import asyncio
import logging
import uuid
from pydantic import BaseModel, Field, PrivateAttr
from typing import Any, Dict, Optional

from llama_index.core.tools import AsyncBaseTool, ToolMetadata, ToolOutput

from llama_deploy.messages.base import QueueMessage
from llama_deploy.message_consumers.base import BaseMessageQueueConsumer
from llama_deploy.message_consumers.callable import CallableMessageConsumer
from llama_deploy.message_queues.base import BaseMessageQueue
from llama_deploy.message_publishers.publisher import (
    MessageQueuePublisherMixin,
    PublishCallback,
)
from llama_deploy.types import (
    ActionTypes,
    ServiceDefinition,
    TaskDefinition,
    ToolCallResult,
)
from llama_deploy.tools.utils import get_tool_name_from_service_name

logger = logging.getLogger(__name__)


class ServiceAsTool(MessageQueuePublisherMixin, AsyncBaseTool, BaseModel):
    """Service As Tool.

    This class is a wrapper around any BaseService, providing a tool-like interface,
    to be used as a tool in any other llama-index abstraction.

    NOTE: The BaseService must be able to process messages with action type: NEW_TOOL_CALL

    Args:
        tool_metadata (ToolMetadata): Tool metadata.
        message_queue (BaseMessageQueue): Message queue.
        service_name (str): Service name.
        publish_callback (Optional[PublishCallback], optional): Publish callback. Defaults to None.
        tool_call_results (Dict[str, ToolCallResult], optional): Tool call results. Defaults to {}.
        timeout (float, optional): Timeout. Defaults to 60.0s.
        step_interval (float, optional): Step interval when polling for a result. Defaults to 0.1s.
        raise_timeout (bool, optional): Raise timeout. Defaults to False.

    Examples:
        ```python
        from llama_deploy import AgentService, ServiceAsTool, SimpleMessageQueue

        message_queue = SimpleMessageQueue()

        agent1_server = AgentService(
            agent=agent1,
            message_queue=message_queue,
            description="Useful for getting the secret fact.",
            service_name="secret_fact_agent",
        )

        # create the tool for use in other agents
        agent1_server_tool = ServiceAsTool.from_service_definition(
            message_queue=message_queue,
            service_definition=agent1_server.service_definition
        )

        # can also use the tool directly
        result = await agent1_server_tool.acall(input="get the secret fact")
        print(result)
        ```
    """

    tool_call_results: Dict[str, ToolCallResult] = Field(default_factory=dict)
    timeout: float = Field(default=10.0, description="timeout interval in seconds.")
    service_name: str = Field(default_factory=str)
    step_interval: float = 0.1
    raise_timeout: bool = False
    registered: bool = False

    _message_queue: BaseMessageQueue = PrivateAttr()
    _publisher_id: str = PrivateAttr()
    _publish_callback: Optional[PublishCallback] = PrivateAttr()
    _lock: asyncio.Lock = PrivateAttr()
    _metadata: ToolMetadata = PrivateAttr()

    def __init__(
        self,
        tool_metadata: ToolMetadata,
        message_queue: BaseMessageQueue,
        service_name: str,
        publish_callback: Optional[PublishCallback] = None,
        tool_call_results: Dict[str, ToolCallResult] = {},
        timeout: float = 60.0,
        step_interval: float = 0.1,
        raise_timeout: bool = False,
    ) -> None:
        # validate fn_schema
        if "input" not in tool_metadata.get_parameters_dict()["properties"]:
            raise ValueError("Invalid FnSchema - 'input' field is required.")

        # validate tool name
        if tool_metadata.name != get_tool_name_from_service_name(service_name):
            raise ValueError("Tool name must be in the form '{{service_name}}-as-tool'")

        super().__init__(
            tool_call_results=tool_call_results,
            timeout=timeout,
            step_interval=step_interval,
            service_name=service_name,
            raise_timeout=raise_timeout,
        )
        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback
        self._metadata = tool_metadata
        self._lock = asyncio.Lock()

    @classmethod
    def from_service_definition(
        cls,
        message_queue: BaseMessageQueue,
        service_definition: ServiceDefinition,
        publish_callback: Optional[PublishCallback] = None,
        timeout: float = 60.0,
        step_interval: float = 0.1,
        raise_timeout: bool = False,
    ) -> "ServiceAsTool":
        """Create an ServiceAsTool from a ServiceDefinition.

        Args:
            message_queue (BaseMessageQueue): Message queue.
            service_definition (ServiceDefinition): Service definition.
            publish_callback (Optional[PublishCallback], optional): Publish callback. Defaults to None.
            timeout (float, optional): Timeout. Defaults to 60.0s.
            step_interval (float, optional): Step interval. Defaults to 0.1s.
            raise_timeout (bool, optional): Raise timeout. Defaults to False.
        """
        tool_metadata = ToolMetadata(
            description=service_definition.description,
            name=get_tool_name_from_service_name(service_definition.service_name),
        )
        return cls(
            tool_metadata=tool_metadata,
            message_queue=message_queue,
            service_name=service_definition.service_name,
            publish_callback=publish_callback,
            timeout=timeout,
            step_interval=step_interval,
            raise_timeout=raise_timeout,
        )

    @property
    def message_queue(self) -> BaseMessageQueue:
        """The message queue used by the tool service."""
        return self._message_queue

    @property
    def publisher_id(self) -> str:
        """The publisher ID."""
        return self._publisher_id

    @property
    def publish_callback(self) -> Optional[PublishCallback]:
        """The publish callback, if any."""
        return self._publish_callback

    @property
    def metadata(self) -> ToolMetadata:
        """The tool metadata."""
        return self._metadata

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock

    async def process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        """Process a message from the message queue."""
        if message.action == ActionTypes.COMPLETED_TOOL_CALL:
            tool_call_result = ToolCallResult(**message.data or {})
            async with self.lock:
                self.tool_call_results.update({tool_call_result.id_: tool_call_result})
        else:
            raise ValueError(f"Unhandled action: {message.action}")

    def as_consumer(self) -> BaseMessageQueueConsumer:
        """Return a message queue consumer for this tool."""
        return CallableMessageConsumer(
            id_=self.publisher_id,
            message_type=self.publisher_id,
            handler=self.process_message,
        )

    async def purge_old_tool_call_results(self, cutoff_date: str) -> None:
        """Purge old tool call results.

        TODO: implement this.
        """
        pass

    async def _poll_for_tool_call_result(self, tool_call_id: str) -> ToolCallResult:
        tool_call_result = None
        while tool_call_result is None:
            async with self.lock:
                tool_call_result = (
                    self.tool_call_results[tool_call_id]
                    if tool_call_id in self.tool_call_results
                    else None
                )

            await asyncio.sleep(self.step_interval)
        return tool_call_result

    async def deregister(self) -> None:
        """Deregister from message queue."""
        await self.message_queue.deregister_consumer(self.as_consumer())
        self.registered = False

    def call(self, *args: Any, **kwargs: Any) -> ToolOutput:
        """Publish a call to the queue.

        In order to get a ToolOutput result, this will poll the queue until
        the result is written.
        """
        return asyncio.run(self.acall(*args, **kwargs))

    def _parse_args(self, *args: Any, **kwargs: Any) -> str:
        return kwargs.pop("input")

    async def acall(self, *args: Any, **kwargs: Any) -> ToolOutput:
        """Publish a call to the queue.

        In order to get a ToolOutput result, this will poll the queue until
        the result is written.
        """
        if not self.registered:
            # register tool to message queue
            start_consuming_callable = await self.message_queue.register_consumer(
                self.as_consumer()
            )
            _ = asyncio.create_task(start_consuming_callable())
            self.registered = True

        input = self._parse_args(*args, **kwargs)
        task_def = TaskDefinition(input=input)
        await self.publish(
            QueueMessage(
                type=self.service_name,
                action=ActionTypes.NEW_TOOL_CALL,
                data=task_def.model_dump(),
            )
        )

        # poll for tool_call_result with max timeout
        try:
            tool_call_result = await asyncio.wait_for(
                self._poll_for_tool_call_result(tool_call_id=task_def.task_id),
                timeout=self.timeout,
            )
        except (
            asyncio.exceptions.TimeoutError,
            asyncio.TimeoutError,
            TimeoutError,
        ) as e:
            logger.debug(f"Timeout reached for tool_call with id {task_def.task_id}")
            if self.raise_timeout:
                raise
            return ToolOutput(
                content="Encountered error: " + str(e),
                tool_name=self.metadata.name,
                raw_input={"args": args, "kwargs": kwargs},
                raw_output=str(e),
                is_error=True,
            )
        finally:
            async with self.lock:
                if task_def.task_id in self.tool_call_results:
                    del self.tool_call_results[task_def.task_id]

        return ToolOutput(
            content=tool_call_result.result,
            tool_name=self.metadata.name,
            raw_input={"args": args, "kwargs": kwargs},
            raw_output=tool_call_result.result,
        )
