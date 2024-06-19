import asyncio
import uuid
import uvicorn
from asyncio import Lock
from contextlib import asynccontextmanager
from fastapi import FastAPI
from typing import Any, AsyncGenerator, Dict, List, Optional

from llama_index.core.agent.function_calling.step import (
    get_function_by_name,
)
from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.tools import BaseTool

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
)


class ToolService(BaseService):
    service_name: str
    tools: List[BaseTool]
    description: str = "Local Tool Service."
    running: bool = True
    step_interval: float = 0.1

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
    ) -> None:
        super().__init__(
            tools=tools or [],
            running=running,
            description=description,
            service_name=service_name,
            step_interval=step_interval,
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

            async with self.lock:
                current_tool_calls: List[ToolCall] = [
                    *self._outstanding_tool_calls.values()
                ]
            for tool_call in current_tool_calls:
                tool = get_function_by_name(
                    self.tools, tool_call.tool_call_bundle.tool_name
                )

                tool_output = tool(
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
                        ).dict(),
                    )
                )

                # clean up
                async with self.lock:
                    del self._outstanding_tool_calls[tool_call.id_]

            await asyncio.sleep(self.step_interval)

    async def process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        if message.action == ActionTypes.NEW_TOOL_CALL:
            tool_call_data = {"source_id": message.publisher_id}
            tool_call_data.update(message.data or {})
            tool_call = ToolCall(**tool_call_data)
            async with self.lock:
                self._outstanding_tool_calls.update({tool_call.id_: tool_call})
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
        async with self.lock:
            self._outstanding_tool_calls.update({tool_call.id_: tool_call})
        return {"tool_call_id": tool_call.id_}

    async def get_tool_by_name(self, name: str) -> Dict[str, Any]:
        name_to_tool = {tool.metadata.name: tool for tool in self.tools}
        if name not in name_to_tool:
            raise ValueError(f"Tool with name {name} not found")
        return {"tool_metadata": name_to_tool[name].metadata}

    async def launch_server(self) -> None:
        uvicorn.run(self._app)
