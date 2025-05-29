import asyncio
import hashlib
import json
import os
import uuid
from asyncio.exceptions import CancelledError
from collections import defaultdict
from logging import getLogger
from typing import Any, Dict, Optional

import httpx
from llama_index.core.workflow import Context, Workflow
from llama_index.core.workflow.context_serializers import (
    JsonPickleSerializer,
    JsonSerializer,
)
from llama_index.core.workflow.handler import WorkflowHandler
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from llama_deploy.control_plane.server import (
    CONTROL_PLANE_MESSAGE_TYPE,
    ControlPlaneConfig,
)
from llama_deploy.message_queues.base import AbstractMessageQueue, PublishCallback
from llama_deploy.types import (
    ActionTypes,
    QueueMessage,
    ServiceDefinition,
    TaskDefinition,
    TaskResult,
    TaskStream,
)

logger = getLogger(__name__)
hash_secret = os.environ.get("LLAMA_DEPLOY_WF_SERVICE_HASH_SECRET", "default")


def _make_hash(context_str: str) -> str:
    h = hashlib.sha256()
    content = context_str + hash_secret
    h.update(content.encode())
    return h.hexdigest()


class WorkflowServiceConfig(BaseSettings):
    """Workflow service configuration."""

    model_config = SettingsConfigDict(env_prefix="LLAMA_DEPLOY_WF_SERVICE_")

    host: str
    port: int
    internal_host: Optional[str] = None
    internal_port: Optional[int] = None
    service_name: str = "default_workflow_service"
    description: str = "A service that wraps a llama-index workflow."
    step_interval: float = 0.1
    max_concurrent_tasks: int = 8
    raise_exceptions: bool = False
    use_tls: bool = False

    @property
    def url(self) -> str:
        if self.use_tls:
            return f"https://{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"


class WorkflowState(BaseModel):
    """Holds the state of the workflow.

    Used to validate and pass message payloads.

    TODO: Should this be the general payload for all messages?
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    hash: Optional[str] = Field(
        default=None, description="Hash of the context, if any."
    )
    state: dict = Field(default_factory=dict, description="Pickled state, if any.")
    run_kwargs: Dict[str, Any] = Field(
        default_factory=dict, description="Run kwargs needed to run the workflow."
    )
    session_id: Optional[str] = Field(
        default=None, description="Session ID for the current task."
    )
    task_id: str = Field(description="Task ID for the current run.")


class WorkflowService:
    """Workflow service.

    Wraps a llama-index workflow into a service.
    """

    def __init__(
        self,
        workflow: Workflow,
        message_queue: AbstractMessageQueue,
        config: WorkflowServiceConfig,
        publish_callback: Optional[PublishCallback] = None,
    ) -> None:
        self._service_name = config.service_name
        self._control_plane_config = ControlPlaneConfig()
        self._control_plane_url = self._control_plane_config.url

        self.workflow = workflow
        self.config = config

        self._lock = asyncio.Lock()
        self._running = True
        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback

        self._outstanding_calls: Dict[str, WorkflowState] = {}
        self._ongoing_tasks: Dict[str, asyncio.Task] = {}
        self._events_buffer: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

    @property
    def service_name(self) -> str:
        return self._service_name

    @property
    def service_definition(self) -> ServiceDefinition:
        """Service definition."""
        return ServiceDefinition(
            service_name=self.config.service_name,
            description=self.config.description,
            host=self.config.host,
            port=self.config.port,
        )

    @property
    def message_queue(self) -> AbstractMessageQueue:
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

    async def get_workflow_state(self, state: WorkflowState) -> Optional[Context]:
        """Load the existing context from the workflow state.

        TODO: Support managing the workflow state?
        """
        if state.session_id is None:
            return None

        state_dict = await self.get_session_state(state.session_id)
        if state_dict is None:
            return None

        workflow_state_json = state_dict.get(state.session_id, None)

        if workflow_state_json is None:
            return None

        workflow_state = WorkflowState.model_validate_json(workflow_state_json)
        if workflow_state.state is None:
            return None

        context_dict = workflow_state.state
        context_str = json.dumps(context_dict)
        context_hash = _make_hash(context_str)

        if workflow_state.hash is not None and context_hash != workflow_state.hash:
            raise ValueError("Context hash does not match!")

        return Context.from_dict(
            self.workflow,
            workflow_state.state,
            serializer=JsonPickleSerializer(),
        )

    async def set_workflow_state(
        self, ctx: Context, current_state: WorkflowState
    ) -> None:
        """Set the workflow state for this session."""
        context_dict = ctx.to_dict(serializer=JsonPickleSerializer())
        context_str = json.dumps(context_dict)
        context_hash = _make_hash(context_str)

        workflow_state = WorkflowState(
            hash=context_hash,
            state=context_dict,
            run_kwargs=current_state.run_kwargs,
            session_id=current_state.session_id,
            task_id=current_state.task_id,
        )

        if current_state.session_id is None:
            raise ValueError("Session ID is None! Cannot set workflow state.")

        session_state = await self.get_session_state(current_state.session_id)
        if session_state:
            session_state[current_state.session_id] = workflow_state.model_dump_json()

            # Store the state in the control plane
            await self.update_session_state(current_state.session_id, session_state)

    async def process_call(self, current_call: WorkflowState) -> None:
        """Processes a given task, and writes a response to the message queue.

        Handles errors with a generic try/except, and publishes the error message
        as the result.

        Args:
            current_call (WorkflowState):
                The state of the current task, including run_kwargs and other session state.
        """
        # create send_event background task
        close_send_events = asyncio.Event()
        handler = None

        try:
            # load the state
            ctx = await self.get_workflow_state(current_call)

            # run the workflow
            handler = self.workflow.run(ctx=ctx, **current_call.run_kwargs)
            if handler.ctx is None:
                # This should never happen, workflow.run actually sets the Context
                # even if handler.ctx is typed as Optional[Context]
                raise ValueError("Context cannot be None.")

            async def send_events(
                handler: WorkflowHandler, close_event: asyncio.Event
            ) -> None:
                if handler.ctx is None:
                    raise ValueError("handler does not have a valid Context.")

                while not close_event.is_set():
                    try:
                        event = self._events_buffer[current_call.task_id].get_nowait()
                        handler.ctx.send_event(event)
                    except asyncio.QueueEmpty:
                        pass
                    await asyncio.sleep(self.config.step_interval)

            _ = asyncio.create_task(send_events(handler, close_send_events))

            index = 0
            async for ev in handler.stream_events():
                # send the event to control plane for client / api server streaming
                logger.debug(f"Publishing event: {ev}")
                await self.message_queue.publish(
                    QueueMessage(
                        type=CONTROL_PLANE_MESSAGE_TYPE,
                        action=ActionTypes.TASK_STREAM,
                        data=TaskStream(
                            task_id=current_call.task_id,
                            session_id=current_call.session_id,
                            data=ev.model_dump(),
                            index=index,
                        ).model_dump(),
                    ),
                    self.get_topic(CONTROL_PLANE_MESSAGE_TYPE),
                )
                index += 1

            final_result = await handler

            # dump the state
            await self.set_workflow_state(handler.ctx, current_call)

            logger.info(
                f"Publishing final result: {final_result} to '{self.get_topic(CONTROL_PLANE_MESSAGE_TYPE)}'"
            )
            await self.message_queue.publish(
                QueueMessage(
                    type=CONTROL_PLANE_MESSAGE_TYPE,
                    action=ActionTypes.COMPLETED_TASK,
                    data=TaskResult(
                        task_id=current_call.task_id,
                        history=[],
                        result=str(final_result),
                        data={},
                    ).model_dump(),
                ),
                self.get_topic(CONTROL_PLANE_MESSAGE_TYPE),
            )
        except Exception as e:
            if self.config.raise_exceptions:
                raise e

            logger.error(
                f"Encountered error in task {current_call.task_id}! {str(e)}",
                exc_info=True,
            )
            # dump the state
            if handler is not None and handler.ctx is not None:
                await self.set_workflow_state(handler.ctx, current_call)

            # return failure
            await self.message_queue.publish(
                QueueMessage(
                    type=CONTROL_PLANE_MESSAGE_TYPE,
                    action=ActionTypes.COMPLETED_TASK,
                    data=TaskResult(
                        task_id=current_call.task_id,
                        history=[],
                        result=str(e),
                        data={},
                    ).model_dump(),
                ),
                self.get_topic(CONTROL_PLANE_MESSAGE_TYPE),
            )
        finally:
            # clean up
            close_send_events.set()
            async with self.lock:
                self._outstanding_calls.pop(current_call.task_id, None)
            self._ongoing_tasks.pop(current_call.task_id, None)

    async def manage_tasks(self) -> None:
        """Acts as a manager to process outstanding tasks from a queue.

        Limits number of tasks in progress to `self.max_concurrent_tasks`.

        If the number of ongoing tasks is greater than or equal to `self.max_concurrent_tasks`,
        they are buffered until there is room to run it.
        """
        while True:
            if not self._running:
                await asyncio.sleep(self.config.step_interval)
                continue

            # Check for completed tasks
            completed_tasks = [
                task for task in self._ongoing_tasks.values() if task.done()
            ]
            for task in completed_tasks:
                task_id = next(k for k, v in self._ongoing_tasks.items() if v == task)
                self._ongoing_tasks.pop(task_id, None)

            # Start new tasks
            async with self.lock:
                new_calls = [
                    (t, c)
                    for t, c in self._outstanding_calls.items()
                    if t not in self._ongoing_tasks
                ]

            for task_id, current_call in new_calls:
                if len(self._ongoing_tasks) >= self.config.max_concurrent_tasks:
                    break
                task = asyncio.create_task(self.process_call(current_call))
                self._ongoing_tasks[task_id] = task

            await asyncio.sleep(0.1)  # Small sleep to prevent busy-waiting

    async def processing_loop(self) -> None:
        """The processing loop for the service with non-blocking concurrent task execution."""
        logger.info("Processing initiated.")
        try:
            await self.manage_tasks()
        except CancelledError:
            return

    async def _process_messages(self, topic: str) -> None:
        try:
            async for message in self._message_queue.get_messages(topic):
                if message.action == ActionTypes.NEW_TASK:
                    task_def = TaskDefinition(**message.data or {})

                    run_kwargs = json.loads(task_def.input)
                    workflow_state = WorkflowState(
                        session_id=task_def.session_id,
                        task_id=task_def.task_id,
                        run_kwargs=run_kwargs,
                    )

                    async with self.lock:
                        self._outstanding_calls[task_def.task_id] = workflow_state
                elif message.action == ActionTypes.SEND_EVENT:
                    serializer = JsonSerializer()

                    task_def = TaskDefinition(**message.data or {})
                    event = serializer.deserialize(task_def.input)
                    async with self.lock:
                        self._events_buffer[task_def.task_id].put_nowait(event)

                else:
                    raise ValueError(f"Unhandled action: {message.action}")
        except asyncio.CancelledError:
            pass

    async def launch_server(self) -> None:
        tasks = [
            asyncio.create_task(self.processing_loop()),
            asyncio.create_task(
                self._process_messages(self.get_topic(self.service_name))
            ),
        ]

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks)

    async def register_to_control_plane(self, control_plane_url: str) -> None:
        """Register the service to the control plane."""
        self._control_plane_url = control_plane_url
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{control_plane_url}/services/register",
                json=self.service_definition.model_dump(),
            )
            response.raise_for_status()
            self._control_plane_config = ControlPlaneConfig(**response.json())

    async def deregister_from_control_plane(self) -> None:
        """Deregister the service from the control plane."""
        if not self._control_plane_url:
            raise ValueError(
                "Control plane URL not set. Call register_to_control_plane first."
            )
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._control_plane_url}/services/deregister",
                params={"service_name": self.service_name},
            )
            response.raise_for_status()

    async def get_session_state(self, session_id: str) -> dict[str, Any] | None:
        """Get the session state from the control plane."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._control_plane_url}/sessions/{session_id}/state"
                )
                if response.status_code == 404:
                    return None
                else:
                    response.raise_for_status()

                return response.json()
        except httpx.ConnectError:
            # Let the service live without a control plane running
            return None

    async def update_session_state(
        self, session_id: str, state: dict[str, Any]
    ) -> None:
        """Update the session state in the control plane."""
        if not self._control_plane_url:
            return

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._control_plane_url}/sessions/{session_id}/state",
                json=state,
            )
            response.raise_for_status()

    def get_topic(self, msg_type: str) -> str:
        return f"{self._control_plane_config.topic_namespace}.{msg_type}"
