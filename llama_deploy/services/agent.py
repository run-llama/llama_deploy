import asyncio
import uuid
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from logging import getLogger
from pydantic import PrivateAttr
from typing import AsyncGenerator, Dict, List, Literal, Optional

from llama_index.core.agent import AgentRunner

from llama_deploy.message_consumers.base import BaseMessageQueueConsumer
from llama_deploy.message_consumers.callable import CallableMessageConsumer
from llama_deploy.message_consumers.remote import RemoteMessageConsumer
from llama_deploy.message_publishers.publisher import PublishCallback
from llama_deploy.message_queues.base import BaseMessageQueue
from llama_deploy.messages.base import QueueMessage
from llama_deploy.services.base import BaseService
from llama_deploy.services.types import _ChatMessage
from llama_deploy.types import (
    ActionTypes,
    ChatMessage,
    MessageRole,
    NewTask,
    TaskResult,
    TaskDefinition,
    ToolCall,
    ToolCallBundle,
    ToolCallResult,
    ServiceDefinition,
    CONTROL_PLANE_NAME,
)
from llama_deploy.tools.utils import get_tool_name_from_service_name

logger = getLogger(__name__)


class AgentService(BaseService):
    """Agent Service.

    A service that runs an agent locally, processing incoming tasks step-wise in an endless loop.

    Messages are published to the message queue, and the agent processes them in a loop,
    finally returning a message with the completed task.

    This AgentService can either be run in a local loop or as a Fast-API server.

    Exposes the following endpoints:
    - GET `/`: Home endpoint.
    - POST `/process_message`: Process a message.
    - POST `/task`: Create a task.
    - GET `/messages`: Get messages.
    - POST `/toggle_agent_running`: Toggle the agent running state.
    - GET `/is_worker_running`: Check if the agent is running.
    - POST `/reset_agent`: Reset the agent.

    Since the agent can launch as a FastAPI server, you can visit `/docs` for full swagger documentation.

    Attributes:
        service_name (str):
            The name of the service.
        agent (AgentRunner):
            The agent to run.
        description (str):
            The description of the service.
        prompt (Optional[List[ChatMessage]]):
            The prompt messages, meant to be appended to the start of tasks (currently TODO).
        running (bool):
            Whether the agent is running.
        step_interval (float):
            The interval in seconds to poll for task completion. Defaults to 0.1s.
        host (Optional[str]):
            The host to launch a FastAPI server on.
        port (Optional[int]):
            The port to launch a FastAPI server on.
        raise_exceptions (bool):
            Whether to raise exceptions in the processing loop.

    Examples:
        ```python
        from llama_deploy import AgentService
        from llama_index.core.agent import ReActAgent

        agent = ReActAgent.from_tools([...], llm=llm)
        agent_service = AgentService(
            agent,
            message_queue,
            service_name="my_agent_service",
            description="My Agent Service",
            host="127.0.0.1",
            port=8003,
        )

        # launch as a server for remote access or documentation
        await agent_service.launch_server()
        ```
    """

    service_name: str
    agent: AgentRunner
    description: str = "Local Agent Service."
    prompt: Optional[List[ChatMessage]] = None
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
    _tasks_as_tool_calls: Dict[str, ToolCall] = PrivateAttr()

    def __init__(
        self,
        agent: AgentRunner,
        message_queue: BaseMessageQueue,
        running: bool = True,
        description: str = "Agent Server",
        service_name: str = "default_agent",
        prompt: Optional[List[ChatMessage]] = None,
        publish_callback: Optional[PublishCallback] = None,
        step_interval: float = 0.1,
        host: Optional[str] = None,
        port: Optional[int] = None,
        raise_exceptions: bool = False,
    ) -> None:
        super().__init__(
            agent=agent,
            running=running,
            description=description,
            service_name=service_name,
            step_interval=step_interval,
            prompt=prompt,
            host=host,
            port=port,
            raise_exceptions=raise_exceptions,
        )

        self._lock = asyncio.Lock()
        self._tasks_as_tool_calls = {}
        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback
        self._app = FastAPI(lifespan=self.lifespan)

        self._app.add_api_route("/", self.home, methods=["GET"], tags=["Agent State"])

        self._app.add_api_route(
            "/process_message",
            self.process_message,
            methods=["POST"],
            tags=["Message Processing"],
        )

        self._app.add_api_route(
            "/task", self.create_task, methods=["POST"], tags=["Tasks"]
        )

        self._app.add_api_route(
            "/messages", self.get_messages, methods=["GET"], tags=["Agent State"]
        )
        self._app.add_api_route(
            "/toggle_agent_running",
            self.toggle_agent_running,
            methods=["POST"],
            tags=["Agent State"],
        )
        self._app.add_api_route(
            "/is_worker_running",
            self.is_worker_running,
            methods=["GET"],
            tags=["Agent State"],
        )
        self._app.add_api_route(
            "/reset_agent", self.reset_agent, methods=["POST"], tags=["Agent State"]
        )

    @property
    def service_definition(self) -> ServiceDefinition:
        """The service definition."""
        return ServiceDefinition(
            service_name=self.service_name,
            description=self.description,
            prompt=self.prompt or [],
            host=self.host,
            port=self.port,
        )

    @property
    def message_queue(self) -> BaseMessageQueue:
        """The message queue."""
        return self._message_queue

    @property
    def publisher_id(self) -> str:
        """The publisher id."""
        return self._publisher_id

    @property
    def publish_callback(self) -> Optional[PublishCallback]:
        """The publish callback, if any."""
        return self._publish_callback

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock

    @property
    def tool_name(self) -> str:
        """The name reserved when this service is used as a tool."""
        return get_tool_name_from_service_name(self.service_name)

    async def processing_loop(self) -> None:
        """The processing loop for the agent."""
        logger.info("Processing initiated.")
        while True:
            try:
                if not self.running:
                    await asyncio.sleep(self.step_interval)
                    continue

                current_tasks = self.agent.list_tasks()
                current_task_ids = [task.task_id for task in current_tasks]

                completed_tasks = self.agent.get_completed_tasks()
                completed_task_ids = [task.task_id for task in completed_tasks]

                for task_id in current_task_ids:
                    if task_id in completed_task_ids:
                        continue

                    step_output = await self.agent.arun_step(task_id)

                    if step_output.is_last:
                        # finalize the response
                        response = self.agent.finalize_response(
                            task_id, step_output=step_output
                        )

                        # convert memory chat messages
                        llama_messages = self.agent.memory.get()
                        history = [ChatMessage(**x.dict()) for x in llama_messages]

                        # publish the completed task
                        async with self.lock:
                            try:
                                tool_call = self._tasks_as_tool_calls.pop(task_id)
                            except KeyError:
                                tool_call = None

                        if tool_call:
                            await self.publish(
                                QueueMessage(
                                    type=tool_call.source_id,
                                    action=ActionTypes.COMPLETED_TOOL_CALL,
                                    data=ToolCallResult(
                                        id_=tool_call.id_,
                                        tool_message=ChatMessage(
                                            content=str(response.response),
                                            role=MessageRole.TOOL,
                                            additional_kwargs={
                                                "name": tool_call.tool_call_bundle.tool_name,
                                                "tool_call_id": tool_call.id_,
                                            },
                                        ),
                                        result=response.response,
                                    ).model_dump(),
                                )
                            )
                        else:
                            await self.publish(
                                QueueMessage(
                                    type=CONTROL_PLANE_NAME,
                                    action=ActionTypes.COMPLETED_TASK,
                                    data=TaskResult(
                                        task_id=task_id,
                                        history=history,
                                        result=response.response,
                                    ).model_dump(),
                                )
                            )
            except Exception as e:
                logger.error(f"Error in {self.service_name} processing_loop: {e}")
                if self.raise_exceptions:
                    # Kill everything
                    # TODO: is there a better way to do this?
                    import signal

                    signal.raise_signal(signal.SIGINT)
                else:
                    await self.message_queue.publish(
                        QueueMessage(
                            type=CONTROL_PLANE_NAME,
                            action=ActionTypes.COMPLETED_TASK,
                            data=TaskResult(
                                task_id=task_id,
                                history=[],
                                result=f"Error during processing: {e}",
                            ).model_dump(),
                        )
                    )

                continue

            await asyncio.sleep(self.step_interval)

    async def process_message(self, message: QueueMessage) -> None:
        """Handling for when a message is received."""
        if message.action == ActionTypes.NEW_TASK:
            new_task = NewTask(**message.data or {})
            task_def = new_task.task
            self.agent.create_task(task_def.input, task_id=task_def.task_id)
            logger.info(f"Created new task: {task_def.task_id}")
        elif message.action == ActionTypes.NEW_TOOL_CALL:
            task_def = TaskDefinition(**message.data or {})
            async with self.lock:
                tool_call_bundle = ToolCallBundle(
                    tool_name=self.tool_name,
                    tool_args=(),
                    tool_kwargs={"input": task_def.input},
                )
                task_as_tool_call = ToolCall(
                    id_=task_def.task_id,
                    source_id=message.publisher_id,
                    tool_call_bundle=tool_call_bundle,
                )
                self._tasks_as_tool_calls[task_def.task_id] = task_as_tool_call
            self.agent.create_task(task_def.input, task_id=task_def.task_id)
            logger.info(f"Created new tool call as task: {task_def.task_id}")
        else:
            raise ValueError(f"Unhandled action: {message.action}")

    def as_consumer(self, remote: bool = False) -> BaseMessageQueueConsumer:
        """Get the consumer for the message queue.

        Args:
            remote (bool):
                Whether to get a remote consumer or local.
                If remote, calls the `process_message` endpoint.
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
        """Launch the agent locally."""
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
        """Home endpoint. Gets general information about the agent service."""
        tasks = self.agent.list_tasks()

        task_strings = []
        for task in tasks:
            task_output = self.agent.get_task_output(task.task_id)
            status = "COMPLETE" if task_output.is_last else "IN PROGRESS"
            memory_str = "\n".join(
                [f"{x.role}: {x.content}" for x in task.memory.get_all()]
            )
            task_strings.append(f"Agent Task {task.task_id}: {status}\n{memory_str}")

        complete_task_string = "\n".join(task_strings)

        return {
            "service_name": self.service_name,
            "description": self.description,
            "running": str(self.running),
            "step_interval": str(self.step_interval),
            "num_tasks": str(len(tasks)),
            "num_completed_tasks": str(len(self.agent.get_completed_tasks())),
            "prompt": "\n".join([str(x) for x in self.prompt]) if self.prompt else "",
            "type": "agent_service",
            "tasks": complete_task_string,
        }

    async def create_task(self, task: TaskDefinition) -> Dict[str, str]:
        """Create a task."""
        task_id = self.agent.create_task(task, task_id=task.task_id)
        return {"task_id": task_id}

    async def get_messages(self) -> List[_ChatMessage]:
        """Get messages from the agent."""
        messages = self.agent.chat_history

        return [_ChatMessage.from_chat_message(message) for message in messages]

    async def toggle_agent_running(
        self, state: Literal["running", "stopped"]
    ) -> Dict[str, bool]:
        """Toggle the agent running state."""
        self.running = state == "running"

        return {"running": self.running}

    async def is_worker_running(self) -> Dict[str, bool]:
        """Check if the agent is running."""
        return {"running": self.running}

    async def reset_agent(self) -> Dict[str, str]:
        """Reset the agent."""
        self.agent.reset()

        return {"message": "Agent reset"}

    async def launch_server(self) -> None:
        """Launch the agent as a FastAPI server."""
        logger.info(f"Launching {self.service_name} server at {self.host}:{self.port}")
        # uvicorn.run(self._app, host=self.host, port=self.port)

        class CustomServer(uvicorn.Server):
            def install_signal_handlers(self) -> None:
                pass

        cfg = uvicorn.Config(self._app, host=self.host, port=self.port)
        server = CustomServer(cfg)
        await server.serve()
