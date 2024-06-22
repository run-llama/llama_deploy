import asyncio
import logging
import uuid
import uvicorn
from asyncio import Lock
from contextlib import asynccontextmanager
from fastapi import FastAPI
from typing import Any, AsyncGenerator, Dict, List, Optional
from pydantic import PrivateAttr

from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.message_consumers.callable import CallableMessageConsumer
from agentfile.message_consumers.remote import RemoteMessageConsumer
from agentfile.message_publishers.publisher import PublishCallback
from agentfile.message_queues.base import BaseMessageQueue
from agentfile.messages.base import QueueMessage
from agentfile.services.base import BaseService
from agentfile.types import (
    ActionTypes,
    TaskDefinition,
    TaskResult,
    ServiceDefinition,
    CONTROL_PLANE_NAME,
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
    host: Optional[str] = None
    port: Optional[int] = None

    _outstanding_human_requests: Dict[str, TaskDefinition] = PrivateAttr()
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
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> None:
        super().__init__(
            running=running,
            description=description,
            service_name=service_name,
            step_interval=step_interval,
            host=host,
            port=port,
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
                current_requests: List[TaskDefinition] = [
                    *self._outstanding_human_requests.values()
                ]
            for task_def in current_requests:
                logger.info(
                    f"Processing request for human help for task: {task_def.task_id}"
                )

                # process req
                result = input(
                    HELP_REQUEST_TEMPLATE_STR.format(input_str=task_def.input)
                )
                logger.info(f"{result}")

                # publish the completed task
                await self.publish(
                    QueueMessage(
                        type=CONTROL_PLANE_NAME,
                        action=ActionTypes.COMPLETED_TASK,
                        data=TaskResult(
                            task_id=task_def.task_id,
                            history=[],
                            result=result,
                        ).model_dump(),
                    )
                )

                # clean up
                async with self.lock:
                    del self._outstanding_human_requests[task_def.task_id]

            await asyncio.sleep(self.step_interval)

    async def process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        if message.action == ActionTypes.REQUEST_FOR_HELP:
            task_def = TaskDefinition(**message.data or {})
            async with self.lock:
                self._outstanding_human_requests.update({task_def.task_id: task_def})
        else:
            raise ValueError(f"Unhandled action: {message.action}")

    def as_consumer(self, remote: bool = False) -> BaseMessageQueueConsumer:
        if remote:
            url = f"{self.host}:{self.port}/{self._app.url_path_for('process_message')}"
            return RemoteMessageConsumer(
                url=url,
                message_type=self.service_name,
            )

        return CallableMessageConsumer(
            message_type=self.service_name,
            handler=self.process_message,
        )

    async def launch_local(self) -> None:
        logger.info(f"{self.service_name} launch_local")
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

    async def create_human_request(self, req: TaskDefinition) -> Dict[str, str]:
        async with self.lock:
            self._outstanding_human_requests.update({req.task_id: req})
        return {"human_request_id": req.task_id}

    def launch_server(self) -> None:
        uvicorn.run(self._app, host=self.host, port=self.port)
