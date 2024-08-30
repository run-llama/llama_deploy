import asyncio
import uuid
import uvicorn
from asyncio import Lock
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import PrivateAttr
from logging import getLogger
from typing import Any, AsyncGenerator, Dict, List, Optional

from llama_index.core.agent.function_calling.step import (
    get_function_by_name,
)
from llama_index.core.llms import MessageRole
from llama_index.core.tools import BaseTool, AsyncBaseTool, adapt_to_async_tool

from llama_deploy.message_consumers.base import BaseMessageQueueConsumer
from llama_deploy.message_consumers.callable import CallableMessageConsumer
from llama_deploy.message_consumers.remote import RemoteMessageConsumer
from llama_deploy.message_publishers.publisher import PublishCallback
from llama_deploy.message_queues.base import BaseMessageQueue
from llama_deploy.messages.base import QueueMessage
from llama_deploy.services.base import BaseService
from llama_deploy.types import (
    ActionTypes,
    ChatMessage,
    ToolCall,
    ToolCallResult,
    ServiceDefinition,
)

logger = getLogger(__name__)


class ToolService(BaseService):
    """A service that executes tools remotely for other services.

    This service is responsible for executing tools remotely for other services and agents.

    Exposes the following endpoints:
    - GET `/`: Home endpoint.
    - POST `/tool_call`: Create a tool call.
    - GET `/tool`: Get a tool by name.
    - POST `/process_message`: Process a message.

    Attributes:
        tools (List[AsyncBaseTool]):
            A list of tools to execute.
        description (str):
            The description of the tool service.
        running (bool):
            Whether the service is running.
        step_interval (float):
            The interval in seconds to poll for tool call results. Defaults to 0.1s.
        host (Optional[str]):
            The host of the service.
        port (Optional[int]):
            The port of the service.

    Examples:
        ```python
        from llama_deploy import ToolService, MetaServiceTool, SimpleMessageQueue
        from llama_index.core.llms import OpenAI
        from llama_index.core.agent import FunctionCallingAgentWorker

        message_queue = SimpleMessageQueue()

        tool_service = ToolService(
            message_queue=message_queue,
            tools=[tool],
            running=True,
            step_interval=0.5,
        )

        # create a meta tool and use it in any other agent
        # this allows remote execution of that tool
        meta_tool = MetaServiceTool(
            tool_metadata=tool.metadata,
            message_queue=message_queue,
            tool_service_name=tool_service.service_name,
        )
        agent = FunctionCallingAgentWorker.from_tools(
            [meta_tool],
            llm=OpenAI(),
        ).as_agent()
        ```
    """

    service_name: str
    tools: List[AsyncBaseTool]
    description: str = "Local Tool Service."
    running: bool = True
    step_interval: float = 0.1
    host: Optional[str] = None
    port: Optional[int] = None

    _outstanding_tool_calls: Dict[str, ToolCall] = PrivateAttr()
    _message_queue: BaseMessageQueue = PrivateAttr()
    _app: FastAPI = PrivateAttr()
    _publisher_id: str = PrivateAttr()
    _publish_callback: Optional[PublishCallback] = PrivateAttr()
    _lock: Lock = PrivateAttr()

    def __init__(
        self,
        message_queue: BaseMessageQueue,
        tools: Optional[List[BaseTool]] = None,
        running: bool = True,
        description: str = "Tool Server",
        service_name: str = "default_tool_service",
        publish_callback: Optional[PublishCallback] = None,
        step_interval: float = 0.1,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> None:
        tools = tools or []
        tools = [adapt_to_async_tool(t) for t in tools]
        super().__init__(
            tools=tools,
            running=running,
            description=description,
            service_name=service_name,
            step_interval=step_interval,
            host=host,
            port=port,
        )

        self._outstanding_tool_calls = {}
        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback
        self._lock = asyncio.Lock()
        self._app = FastAPI(lifespan=self.lifespan)

        self._app.add_api_route("/", self.home, methods=["GET"], tags=["Tool Service"])

        self._app.add_api_route(
            "/tool_call", self.create_tool_call, methods=["POST"], tags=["Tool Call"]
        )

        self._app.add_api_route(
            "/tool", self.get_tool_by_name, methods=["GET"], tags=["Tool"]
        )

        self._app.add_api_route(
            "/process_message",
            self.process_message,
            methods=["POST"],
            tags=["Message Processing"],
        )

    @property
    def service_definition(self) -> ServiceDefinition:
        """The service definition."""
        return ServiceDefinition(
            service_name=self.service_name,
            description=self.description,
            prompt=[],
            host=self.host,
            port=self.port,
        )

    @property
    def message_queue(self) -> BaseMessageQueue:
        """The message queue."""
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
    def lock(self) -> Lock:
        return self._lock

    async def processing_loop(self) -> None:
        """The processing loop for the service."""
        logger.info("Processing initiated.")
        while True:
            if not self.running:
                await asyncio.sleep(self.step_interval)
                continue

            async with self.lock:
                current_tool_calls: List[ToolCall] = [
                    *self._outstanding_tool_calls.values()
                ]
            for tool_call in current_tool_calls:
                tool = get_function_by_name(
                    self.tools, tool_call.tool_call_bundle.tool_name
                )

                logger.info(
                    f"Processing tool call id {tool_call.id_} with {tool.metadata.name}"
                )
                tool_output = await tool.acall(
                    *tool_call.tool_call_bundle.tool_args,
                    **tool_call.tool_call_bundle.tool_kwargs,
                )

                # execute function call
                tool_message = ChatMessage(
                    content=str(tool_output),
                    role=MessageRole.TOOL,
                    additional_kwargs={
                        "name": tool_call.tool_call_bundle.tool_name,
                        "tool_call_id": tool_call.id_,
                    },
                )

                # publish the completed task
                await self.publish(
                    QueueMessage(
                        type=tool_call.source_id,
                        action=ActionTypes.COMPLETED_TOOL_CALL,
                        data=ToolCallResult(
                            id_=tool_call.id_,
                            tool_message=tool_message,
                            result=str(tool_output),
                        ).model_dump(),
                    )
                )

                # clean up
                async with self.lock:
                    del self._outstanding_tool_calls[tool_call.id_]

            await asyncio.sleep(self.step_interval)

    async def process_message(self, message: QueueMessage) -> None:
        """Process a message."""
        if message.action == ActionTypes.NEW_TOOL_CALL:
            tool_call_data = {"source_id": message.publisher_id}
            tool_call_data.update(message.data or {})
            tool_call = ToolCall(**tool_call_data)
            async with self.lock:
                self._outstanding_tool_calls.update({tool_call.id_: tool_call})
        else:
            raise ValueError(f"Unhandled action: {message.action}")

    def as_consumer(self, remote: bool = False) -> BaseMessageQueueConsumer:
        """Get the consumer for the service.

        Args:
            remote (bool):
                Whether the consumer is remote. Defaults to False.
                If True, the consumer will be a RemoteMessageConsumer that uses the `process_message` endpoint.
        """
        if remote:
            url = (
                f"http://{self.host}:{self.port}{self._app.url_path_for('process_message')}"
                if self.port
                else f"http://{self.host}{self._app.url_path_for('process_message')}"
            )
            return RemoteMessageConsumer(
                id_=self.publisher_id,
                url=url,
                message_type=self.service_name,
            )
        return CallableMessageConsumer(
            id_=self.publisher_id,
            message_type=self.service_name,
            handler=self.process_message,
        )

    async def launch_local(self) -> asyncio.Task:
        """Launch the service in-process."""
        return asyncio.create_task(self.processing_loop())

    # ---- Server based methods ----

    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncGenerator[None, None]:
        """Starts the processing loop when the fastapi app starts."""
        asyncio.create_task(self.processing_loop())
        yield
        self.running = False

    async def home(self) -> Dict[str, str]:
        """Home endpoint. Returns the general information about the service."""
        return {
            "service_name": self.service_name,
            "description": self.description,
            "running": str(self.running),
            "step_interval": str(self.step_interval),
            "num_tools": str(len(self.tools)),
            "num_outstanding_tool_calls": str(len(self._outstanding_tool_calls)),
            "tool_calls": "\n".join(
                [str(tool_call) for tool_call in self._outstanding_tool_calls.values()]
            ),
            "type": "tool_service",
        }

    async def create_tool_call(self, tool_call: ToolCall) -> Dict[str, str]:
        """Create a tool call."""
        async with self.lock:
            self._outstanding_tool_calls.update({tool_call.id_: tool_call})
        return {"tool_call_id": tool_call.id_}

    async def get_tool_by_name(self, name: str) -> Dict[str, Any]:
        """Get a tool by name."""
        name_to_tool = {tool.metadata.name: tool for tool in self.tools}
        if name not in name_to_tool:
            raise ValueError(f"Tool with name {name} not found")
        return {"tool_metadata": name_to_tool[name].metadata}

    async def launch_server(self) -> None:
        """Launch the service as a FastAPI server."""
        logger.info(f"Launching tool service server at {self.host}:{self.port}")
        # uvicorn.run(self._app, host=self.host, port=self.port)

        class CustomServer(uvicorn.Server):
            def install_signal_handlers(self) -> None:
                pass

        cfg = uvicorn.Config(self._app, host=self.host, port=self.port)
        server = CustomServer(cfg)
        await server.serve()
