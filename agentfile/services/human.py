import asyncio
import logging
import uuid
import uvicorn
from asyncio import Lock
from contextlib import asynccontextmanager
from fastapi import FastAPI
from typing import Any, AsyncGenerator, Dict, List, Optional

from llama_index.core.bridge.pydantic import PrivateAttr

from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.message_consumers.callable import CallableMessageConsumer
from agentfile.message_publishers.publisher import PublishCallback
from agentfile.message_queues.base import BaseMessageQueue
from agentfile.messages.base import QueueMessage
from agentfile.services.base import BaseService
from agentfile.types import (
    ActionTypes,
    HumanRequest,
    HumanResult,
    ServiceDefinition,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


HELP_REQUEST_TEMPLATE_STR = (
    "Your assistance is needed. Please respond to the request "
    "provided below:\n===\n\n"
    "{input_str}\n\n===\n"
)


class HumanService(BaseService):
    service_name: str
    description: str = "Local Human Service."
    running: bool = True
    step_interval: float = 0.1

    _outstanding_human_requests: Dict[str, HumanRequest] = PrivateAttr()
    _message_queue: BaseMessageQueue = PrivateAttr()
    _app: FastAPI = PrivateAttr()
    _publisher_id: str = PrivateAttr()
    _publish_callback: Optional[PublishCallback] = PrivateAttr()
    _lock: Lock = PrivateAttr()

    def __init__(
        self,
        message_queue: BaseMessageQueue,
        running: bool = True,
        description: str = "Local Human Service",
        service_name: str = "default_human_service",
        publish_callback: Optional[PublishCallback] = None,
        step_interval: float = 0.1,
    ) -> None:
        super().__init__(
            running=running,
            description=description,
            service_name=service_name,
            step_interval=step_interval,
        )

        self._outstanding_human_requests = {}
        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback
        self._lock = asyncio.Lock()
        self._app = FastAPI(lifespan=self.lifespan)

        self._app.add_api_route("/", self.home, methods=["GET"], tags=["Human Service"])

        self._app.add_api_route(
            "/help", self.create_human_request, methods=["POST"], tags=["Help Requests"]
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
                current_requests: List[HumanRequest] = [
                    *self._outstanding_human_requests.values()
                ]
            for req in current_requests:
                logger.info(f"Processing tool call id {req.id_}")

                # process req
                result = input(HELP_REQUEST_TEMPLATE_STR.format(input_str=req.input))

                # publish the completed task
                await self.publish(
                    QueueMessage(
                        type=req.source_id,
                        action=ActionTypes.COMPLETED_REQUEST_FOR_HELP,
                        data=HumanResult(
                            id_=req.id_,
                            result=result,
                        ).dict(),
                    )
                )

                # clean up
                async with self.lock:
                    del self._outstanding_human_requests[req.id_]

            await asyncio.sleep(self.step_interval)

    async def process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        if message.action == ActionTypes.REQUEST_FOR_HELP:
            req_data = {"source_id": message.publisher_id}
            req_data.update(message.data or {})
            req = HumanRequest(**req_data)
            async with self.lock:
                self._outstanding_human_requests.update({req.id_: req})
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

    async def create_human_request(self, req: HumanRequest) -> Dict[str, str]:
        async with self.lock:
            self._outstanding_human_requests.update({req.id_: req})
        return {"human_request_id": req.id_}

    async def launch_server(self) -> None:
        uvicorn.run(self._app)
