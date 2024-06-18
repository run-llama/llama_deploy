import asyncio
import uuid
from asyncio import Lock
from contextlib import asynccontextmanager
from fastapi import FastAPI
from typing import Any, AsyncGenerator, Dict, List, Optional

from llama_index.core.agent.function_calling.step import (
    build_missing_tool_output,
    get_function_by_name,
)
from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.tools import BaseTool, ToolSelection
from llama_index.core.tools.calling import (
    acall_tool_with_selection,
)

from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.message_consumers.callable import CallableMessageConsumer
from agentfile.message_publishers.publisher import PublishCallback
from agentfile.message_queues.base import BaseMessageQueue
from agentfile.messages.base import QueueMessage
from agentfile.services.base import BaseService
from agentfile.types import (
    ActionTypes,
    ToolCall,
    ToolCallResult,
    ServiceDefinition,
    CONTROL_PLANE_NAME,
)


class ToolService(BaseService):
    service_name: str
    tools: List[BaseTool]
    description: str = "Local Tool Service."
    running: bool = True
    step_interval: float = 0.1

    _outstanding_tool_calls: List[ToolCall] = PrivateAttr()
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
    ) -> None:
        super().__init__(
            tools=tools or [],
            running=running,
            description=description,
            service_name=service_name,
            step_interval=step_interval,
        )

        self._outstanding_tool_calls = []
        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback
        self._lock = asyncio.Lock()
        self._app = FastAPI(lifespan=self.lifespan)

        self._app.add_api_route("/", self.home, methods=["GET"], tags=["Tool Service"])

        self._app.add_api_route(
            "/tool_call", self.create, methods=["POST"], tags=["Tool"]
        )

        self._app.add_api_route("/tool", self.get_tools, methods=["GET"], tags=["Tool"])

        self._app.add_api_route(
            "/tool", self.register_tool, methods=["POST"], tags=["Tool"]
        )

    @property
    def service_definition(self) -> ServiceDefinition:
        return ServiceDefinition(
            service_name=self.service_name,
            description=self.description,
            prompt=[],
        )

    @property
    def message_queue(self) -> BaseMessageQueue:
        return self._message_queue

    @property
    def publisher_id(self) -> str:
        return self._publisher_id

    @property
    def publish_callback(self) -> Optional[PublishCallback]:
        return self._publish_callback

    @property
    def lock(self) -> Lock:
        return self._lock

    async def processing_loop(self) -> None:
        while True:
            if not self.running:
                await asyncio.sleep(self.step_interval)
                continue

            current_tool_calls = [*self._outstanding_tool_calls]
            for tool_call in current_tool_calls:
                tool = get_function_by_name(
                    self.tools, tool_call.tool_selection.tool_name
                )

                tool_output = await (
                    acall_tool_with_selection(tool_call.tool_selection, self.tools)
                    if tool is not None
                    else build_missing_tool_output(tool_call.tool_selection)
                )

                # execute function call
                tool_message = ChatMessage(
                    content=str(tool_output),
                    role=MessageRole.TOOL,
                    additional_kwargs={
                        "name": tool_call.tool_selection.tool_name,
                        "tool_call_id": tool_call.tool_selection.tool_id,
                    },
                )

                # publish the completed task
                await self.publish(
                    QueueMessage(
                        type=CONTROL_PLANE_NAME,
                        action=ActionTypes.COMPLETED_TOOL_CALL,
                        data=ToolCallResult(
                            id_=tool_call.id_,
                            tool_message=tool_message,
                            result=str(tool_output),
                        ).dict(),
                    )
                )

            await asyncio.sleep(self.step_interval)

    async def process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        if message.action == ActionTypes.NEW_TOOL_CALL:
            tool_selection = ToolSelection(**message.data or {})
            async with self.lock:
                self._outstanding_tool_calls.append(tool_selection)
        else:
            raise ValueError(f"Unhandled action: {message.action}")

    def as_consumer(self) -> BaseMessageQueueConsumer:
        return CallableMessageConsumer(
            message_type=self.service_name,
            handler=self.process_message,
        )

    async def launch_local(self) -> None:
        asyncio.create_task(self.processing_loop())

    # ---- Server based methods ----

    @asynccontextmanager
    async def lifespan(self) -> AsyncGenerator[None, None]:
        """Starts the processing loop when the fastapi app starts."""
        asyncio.create_task(self.processing_loop())
        yield
        self.running = False

    async def home(self) -> Dict[str, str]:
        return {
            "service_name": self.service_name,
            "description": self.description,
            "running": str(self.running),
            "step_interval": str(self.step_interval),
        }

    async def create_tool_call(self, tool_call: ToolCall) -> Dict[str, str]:
        self._outstanding_tool_calls.append(tool_call)
        return {"tool_call_id": tool_call.id_}
