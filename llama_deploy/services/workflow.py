import asyncio
import base64
import copy
import json
import pickle
import os
import uuid
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from logging import getLogger
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import AsyncGenerator, Dict, Optional, Any

from llama_index.core.workflow import Workflow

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

logger = getLogger(__name__)
hash_secret = str(os.environ.get("llama_deploy_HASH_SECRET", "default"))


class WorkflowServiceConfig(BaseSettings):
    """Workflow service configuration."""

    model_config = SettingsConfigDict(env_prefix="WORKFLOW_SERVICE_")

    host: str
    port: int
    internal_host: Optional[str] = None
    internal_port: Optional[int] = None
    service_name: str
    description: str = "A service that wraps a llama-index workflow."
    running: bool = True
    step_interval: float = 0.1
    raise_exceptions: bool = False


class WorkflowState(BaseModel):
    """Holds the state of the workflow.

    Used to validate and pass message payloads.

    TODO: Should this be the general payload for all messages?
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    hash: Optional[int] = Field(
        default=None, description="Hash of the context, if any."
    )
    state: Optional[str] = Field(default=None, description="Pickled state, if any.")
    run_kwargs: Dict[str, Any] = Field(
        default_factory=dict, description="Run kwargs needed to run the workflow."
    )


class WorkflowService(BaseService):
    """Workflow service.

    Wraps a llama-index workflow into a service.

    Exposes the following endpoints:
    - GET `/`: Home endpoint.
    - POST `/process_message`: Process a message.

    Attributes:
        workflow (Workflow): The workflow itself.
        description (str): The description of the service.
        running (bool): Whether the service is running.
        step_interval (float): The interval in seconds to poll for tool call results. Defaults to 0.1s.
        host (Optional[str]): The host of the service.
        port (Optional[int]): The port of the service.
        raise_exceptions (bool): Whether to raise exceptions.

    Examples:
        ```python
        from llama_deploy import WorkflowService
        from llama_index.core.workflow import Workflow

        workflow_service = WorkflowService(
            workflow,
            message_queue=message_queue,
            description="workflow_service",
            service_name="my_workflow_service",
        )
        ```
    """

    service_name: str
    workflow: Workflow

    description: str = "Workflow service."
    running: bool = True
    step_interval: float = 0.1
    host: Optional[str] = None
    port: Optional[int] = None
    internal_host: Optional[str] = None
    internal_port: Optional[int] = None
    raise_exceptions: bool = False

    _message_queue: BaseMessageQueue = PrivateAttr()
    _app: FastAPI = PrivateAttr()
    _publisher_id: str = PrivateAttr()
    _publish_callback: Optional[PublishCallback] = PrivateAttr()
    _lock: asyncio.Lock = PrivateAttr()
    _outstanding_calls: Dict[str, WorkflowState] = PrivateAttr()

    def __init__(
        self,
        workflow: Workflow,
        message_queue: BaseMessageQueue,
        running: bool = True,
        description: str = "Component Server",
        service_name: str = "default_workflow_service",
        publish_callback: Optional[PublishCallback] = None,
        step_interval: float = 0.1,
        host: Optional[str] = None,
        port: Optional[int] = None,
        internal_host: Optional[str] = None,
        internal_port: Optional[int] = None,
        raise_exceptions: bool = False,
    ) -> None:
        super().__init__(
            workflow=workflow,
            running=running,
            description=description,
            service_name=service_name,
            step_interval=step_interval,
            host=host,
            port=port,
            internal_host=internal_host,
            internal_port=internal_port,
            raise_exceptions=raise_exceptions,
        )

        self._lock = asyncio.Lock()
        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback

        self._outstanding_calls: Dict[str, WorkflowState] = {}

        self._app = FastAPI(lifespan=self.lifespan)

        self._app.add_api_route(
            "/", self.home, methods=["GET"], tags=["Workflow Service"]
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

    def load_workflow_state(self, workflow: Workflow, state: WorkflowState) -> Workflow:
        """Fork the workflow with the given state.

        TODO: Workflows should have a more explicit way to insert state.
        TODO: This is a bit of a hack.
        If the context was limited to seriazbale types, this would be easier.
        """
        context_hash = state.hash
        context_str = state.state
        if not context_str:
            return workflow

        if hash(context_str + hash_secret) != context_hash:
            raise ValueError("Context hash does not match. Possible data corruption.")

        # only load context once it's been verified(?)
        # convert str to bytes
        context_bytes = base64.b64decode(context_str)
        context = pickle.loads(context_bytes)
        workflow._root_context = context

        return workflow

    def dump_workflow_state(
        self, workflow: Workflow, run_kawrgs: dict
    ) -> WorkflowState:
        """Dump the workflow state.

        TODO: This is a bit of a hack.
        If the context was limited to seriazbale types, this would be easier.
        """
        context = workflow._root_context
        context_bytes = pickle.dumps(context)
        context_str = base64.b64encode(context_bytes).decode("ascii")
        context_hash = hash(context_str + hash_secret)

        return WorkflowState(
            hash=context_hash, state=context_str, run_kwargs=run_kawrgs
        )

    async def processing_loop(self) -> None:
        """The processing loop for the service.

        TODO: How do we handle any errors that occur during processing?
        """
        logger.info("Processing initiated.")
        while True:
            if not self.running:
                await asyncio.sleep(self.step_interval)
                continue

            async with self.lock:
                current_calls = [(t, c) for t, c in self._outstanding_calls.items()]

            for task_id, current_call in current_calls:
                # "fork" the workflow, clear its state
                self.workflow._queues = {}
                self.workflow._root_context = {}
                self.workflow._tasks = set()
                self.workflow._step_to_context = {}
                workflow = copy.deepcopy(self.workflow)

                # load the state
                workflow = self.load_workflow_state(workflow, current_call)

                # run the workflow
                # TODO: How do we handle streaming? Websockets?
                result = await workflow.run(**current_call.run_kwargs)

                # dump the state
                updated_state = self.dump_workflow_state(
                    workflow, current_call.run_kwargs
                )

                await self.message_queue.publish(
                    QueueMessage(
                        type=CONTROL_PLANE_NAME,
                        action=ActionTypes.COMPLETED_TASK,
                        data=TaskResult(
                            task_id=task_id,
                            history=[],
                            result=str(result),
                            data=updated_state.dict(),
                        ).model_dump(),
                    )
                )

                # clean up
                async with self.lock:
                    self._outstanding_calls.pop(task_id, None)

            await asyncio.sleep(self.step_interval)

    async def process_message(self, message: QueueMessage) -> None:
        """Process a message received from the message queue."""
        if message.action == ActionTypes.NEW_TASK:
            new_task = NewTask(**message.data or {})
            async with self.lock:
                new_task.state["run_kwargs"] = json.loads(new_task.task.input)
                workflow_state = WorkflowState(
                    **new_task.state,
                )
                self._outstanding_calls[new_task.task.task_id] = workflow_state
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
            "type": "workflow_service",
        }

    async def launch_server(self) -> None:
        """Launch the service as a FastAPI server."""
        host = self.internal_host or self.host
        port = self.internal_port or self.port
        logger.info(f"Launching {self.service_name} server at {host}:{port}")

        class CustomServer(uvicorn.Server):
            def install_signal_handlers(self) -> None:
                pass

        cfg = uvicorn.Config(self._app, host=host, port=port)
        server = CustomServer(cfg)
        await server.serve()
