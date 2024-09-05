import asyncio
import uuid
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from logging import getLogger
from llama_index.core.bridge.pydantic import PrivateAttr
from typing import AsyncGenerator, Dict, Optional, Any
import json

from llama_deploy.message_consumers.base import BaseMessageQueueConsumer
from llama_deploy.message_consumers.callable import CallableMessageConsumer
from llama_deploy.message_consumers.remote import RemoteMessageConsumer
from llama_deploy.message_publishers.publisher import PublishCallback
from llama_deploy.message_queues.base import BaseMessageQueue
from llama_deploy.messages.base import QueueMessage
from llama_deploy.services.base import BaseService
from llama_deploy.types import (
    ActionTypes,
    NewTask,
    TaskResult,
    ServiceDefinition,
    CONTROL_PLANE_NAME,
)
from llama_index.core.query_pipeline import QueryComponent

logger = getLogger(__name__)


class ComponentService(BaseService):
    """Component service.

    Wraps a query pipeline component into a service.

    Exposes the following endpoints:
    - GET `/`: Home endpoint.
    - POST `/process_message`: Process a message.

    Attributes:
        component (Any): The query pipeline component.
        description (str): The description of the service.
        running (bool): Whether the service is running.
        step_interval (float): The interval in seconds to poll for tool call results. Defaults to 0.1s.
        host (Optional[str]): The host of the service.
        port (Optional[int]): The port of the service.
        raise_exceptions (bool): Whether to raise exceptions.

    Examples:
        ```python
        from llama_deploy import ComponentService
        from llama_index.core.query_pipeline import QueryComponent

        component_service = ComponentService(
            component=query_component,
            message_queue=message_queue,
            description="component_service",
            service_name="my_component_service",
        )
        ```
    """

    service_name: str
    component: Any

    description: str = "Component service."
    running: bool = True
    step_interval: float = 0.1
    host: Optional[str] = None
    port: Optional[int] = None
    raise_exceptions: bool = False

    _message_queue: BaseMessageQueue = PrivateAttr()
    _app: FastAPI = PrivateAttr()
    _publisher_id: str = PrivateAttr()
    _publish_callback: Optional[PublishCallback] = PrivateAttr()
    _lock: asyncio.Lock = PrivateAttr()
    _outstanding_calls: Dict[str, Any] = PrivateAttr()

    def __init__(
        self,
        component: Any,
        message_queue: BaseMessageQueue,
        running: bool = True,
        description: str = "Component Server",
        service_name: str = "default_component_service",
        publish_callback: Optional[PublishCallback] = None,
        step_interval: float = 0.1,
        host: Optional[str] = None,
        port: Optional[int] = None,
        raise_exceptions: bool = False,
    ) -> None:
        # HACK: QueryComponent is on pydantic v1
        if not isinstance(component, QueryComponent):
            raise ValueError("Component must be a QueryComponent")

        super().__init__(
            component=component,
            running=running,
            description=description,
            service_name=service_name,
            step_interval=step_interval,
            host=host,
            port=port,
            raise_exceptions=raise_exceptions,
        )

        self._lock = asyncio.Lock()
        # self._tasks_as_tool_calls = {}
        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback

        self._outstanding_calls: Dict[str, Any] = {}

        self._app = FastAPI(lifespan=self.lifespan)

        self._app.add_api_route(
            "/", self.home, methods=["GET"], tags=["Component Service"]
        )

        self._app.add_api_route(
            "/process_message",
            self.process_message,
            methods=["POST"],
            tags=["Message Processing"],
        )

    @property
    def service_definition(self) -> ServiceDefinition:
        """Service definition."""
        return ServiceDefinition(
            service_name=self.service_name,
            description=self.description,
            host=self.host,
            port=self.port,
        )

    @property
    def message_queue(self) -> BaseMessageQueue:
        """Message queue."""
        return self._message_queue

    @property
    def publisher_id(self) -> str:
        """Publisher ID."""
        return self._publisher_id

    @property
    def publish_callback(self) -> Optional[PublishCallback]:
        """Publish callback, if any."""
        return self._publish_callback

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock

    async def processing_loop(self) -> None:
        """The processing loop for the service."""
        logger.info("Processing initiated.")
        while True:
            if not self.running:
                await asyncio.sleep(self.step_interval)
                continue

            async with self.lock:
                current_calls = [(t, c) for t, c in self._outstanding_calls.items()]

            for task_id, current_call in current_calls:
                output_dict = await self.component.arun_component(**current_call)

                await self.message_queue.publish(
                    QueueMessage(
                        type=CONTROL_PLANE_NAME,
                        action=ActionTypes.COMPLETED_TASK,
                        data=TaskResult(
                            task_id=task_id,
                            history=[],
                            result=json.dumps(output_dict),
                            data=output_dict,
                        ).model_dump(),
                    )
                )

                # clean up
                async with self.lock:
                    del self._outstanding_calls[task_id]

            await asyncio.sleep(self.step_interval)

    async def process_message(self, message: QueueMessage) -> None:
        """Process a message received from the message queue."""
        if message.action == ActionTypes.NEW_TASK:
            new_task = NewTask(**message.data or {})
            task_def = new_task.task
            async with self.lock:
                self._outstanding_calls[task_def.task_id] = new_task.state[
                    "__input_dict__"
                ]
        else:
            raise ValueError(f"Unhandled action: {message.action}")

    def as_consumer(self, remote: bool = False) -> BaseMessageQueueConsumer:
        """Get the consumer for the message queue.

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
        logger.info(f"{self.service_name} launch_local")
        return asyncio.create_task(self.processing_loop())

    # ---- Server based methods ----

    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncGenerator[None, None]:
        """Starts the processing loop when the fastapi app starts."""
        asyncio.create_task(self.processing_loop())
        yield
        self.running = False

    async def home(self) -> Dict[str, str]:
        """Home endpoint. Returns general information about the service."""
        return {
            "service_name": self.service_name,
            "description": self.description,
            "running": str(self.running),
            "step_interval": str(self.step_interval),
            "num_outstanding_calls": str(len(self._outstanding_calls)),
            "type": "component_service",
        }

    async def launch_server(self) -> None:
        """Launch the service as a FastAPI server."""
        logger.info(f"Launching {self.service_name} server at {self.host}:{self.port}")
        # uvicorn.run(self._app, host=self.host, port=self.port)

        class CustomServer(uvicorn.Server):
            def install_signal_handlers(self) -> None:
                pass

        cfg = uvicorn.Config(self._app, host=self.host, port=self.port)
        server = CustomServer(cfg)
        await server.serve()
