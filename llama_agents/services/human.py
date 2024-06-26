import asyncio
import uuid
import uvicorn
from asyncio import Lock
from fastapi import FastAPI
from logging import getLogger
from pydantic import PrivateAttr
from typing import Dict, List, Optional

from llama_index.core.llms import MessageRole

from llama_agents.message_consumers.base import BaseMessageQueueConsumer
from llama_agents.message_consumers.callable import CallableMessageConsumer
from llama_agents.message_consumers.remote import RemoteMessageConsumer
from llama_agents.message_publishers.publisher import PublishCallback
from llama_agents.message_queues.base import BaseMessageQueue
from llama_agents.messages.base import QueueMessage
from llama_agents.services.base import BaseService
from llama_agents.types import (
    ActionTypes,
    ChatMessage,
    HumanResponse,
    TaskDefinition,
    TaskResult,
    ServiceDefinition,
    CONTROL_PLANE_NAME,
)


logger = getLogger(__name__)


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

    _outstanding_human_tasks: List[TaskDefinition] = PrivateAttr()
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

        self._outstanding_human_tasks = []
        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback
        self._lock = asyncio.Lock()
        self._app = FastAPI()

        self._app.add_api_route("/", self.home, methods=["GET"], tags=["Human Service"])
        self._app.add_api_route(
            "/process_message",
            self.process_message,
            methods=["POST"],
            tags=["Human Service"],
        )

        self._app.add_api_route(
            "/tasks", self.create_task, methods=["POST"], tags=["Tasks"]
        )
        self._app.add_api_route(
            "/tasks", self.get_tasks, methods=["GET"], tags=["Tasks"]
        )
        self._app.add_api_route(
            "/tasks/{task_id}", self.get_task, methods=["GET"], tags=["Tasks"]
        )
        self._app.add_api_route(
            "/tasks/{task_id}/handle",
            self.handle_task,
            methods=["POST"],
            tags=["Tasks"],
        )

    @property
    def service_definition(self) -> ServiceDefinition:
        return ServiceDefinition(
            service_name=self.service_name,
            description=self.description,
            prompt=[],
            host=self.host,
            port=self.port,
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
                try:
                    task_def = self._outstanding_human_tasks.pop(0)
                except IndexError:
                    await asyncio.sleep(self.step_interval)
                    continue

                logger.info(
                    f"Processing request for human help for task: {task_def.task_id}"
                )

                # process req
                result = input(
                    HELP_REQUEST_TEMPLATE_STR.format(input_str=task_def.input)
                )

                # create history
                history = [
                    ChatMessage(
                        role=MessageRole.ASSISTANT,
                        content=HELP_REQUEST_TEMPLATE_STR.format(
                            input_str=task_def.input
                        ),
                    ),
                    ChatMessage(role=MessageRole.USER, content=result),
                ]

                # publish the completed task
                await self.publish(
                    QueueMessage(
                        type=CONTROL_PLANE_NAME,
                        action=ActionTypes.COMPLETED_TASK,
                        data=TaskResult(
                            task_id=task_def.task_id,
                            history=history,
                            result=result,
                        ).model_dump(),
                    )
                )

            await asyncio.sleep(self.step_interval)

    async def process_message(self, message: QueueMessage) -> None:
        if message.action == ActionTypes.NEW_TASK:
            task_def = TaskDefinition(**message.data or {})
            async with self.lock:
                self._outstanding_human_tasks.append(task_def)
        else:
            raise ValueError(f"Unhandled action: {message.action}")

    def as_consumer(self, remote: bool = False) -> BaseMessageQueueConsumer:
        if remote:
            url = f"http://{self.host}:{self.port}{self._app.url_path_for('process_message')}"
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
        logger.info(f"{self.service_name} launch_local")
        return asyncio.create_task(self.processing_loop())

    # ---- Server based methods ----

    async def home(self) -> Dict[str, str]:
        return {
            "service_name": self.service_name,
            "description": self.description,
            "running": str(self.running),
            "step_interval": str(self.step_interval),
            "num_tasks": str(len(self._outstanding_human_tasks)),
            "tasks": "\n".join([str(task) for task in self._outstanding_human_tasks]),
            "type": "human_service",
        }

    async def create_task(self, task: TaskDefinition) -> Dict[str, str]:
        async with self.lock:
            self._outstanding_human_tasks.append(task)
        return {"task_id": task.task_id}

    async def get_tasks(self) -> List[TaskDefinition]:
        async with self.lock:
            return [*self._outstanding_human_tasks]

    async def get_task(self, task_id: str) -> Optional[TaskDefinition]:
        async with self.lock:
            for task in self._outstanding_human_tasks:
                if task.task_id == task_id:
                    return task
        return None

    async def handle_task(self, task_id: str, result: HumanResponse) -> None:
        async with self.lock:
            for task_def in self._outstanding_human_tasks:
                if task_def.task_id == task_id:
                    self._outstanding_human_tasks.remove(task_def)
                    break

        logger.info(f"Processing request for human help for task: {task_def.task_id}")

        # create history
        history = [
            ChatMessage(
                role=MessageRole.ASSISTANT,
                content=HELP_REQUEST_TEMPLATE_STR.format(input_str=task_def.input),
            ),
            ChatMessage(role=MessageRole.USER, content=result.result),
        ]

        # publish the completed task
        await self.publish(
            QueueMessage(
                type=CONTROL_PLANE_NAME,
                action=ActionTypes.COMPLETED_TASK,
                data=TaskResult(
                    task_id=task_def.task_id,
                    history=history,
                    result=result.result,
                ).model_dump(),
            )
        )

    async def launch_server(self) -> None:
        logger.info(
            f"Lanching server for {self.service_name} at {self.host}:{self.port}"
        )

        class CustomServer(uvicorn.Server):
            def install_signal_handlers(self) -> None:
                pass

        cfg = uvicorn.Config(self._app, host=self.host, port=self.port)
        server = CustomServer(cfg)
        await server.serve()
