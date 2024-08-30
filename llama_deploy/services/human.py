import asyncio
import uuid
import uvicorn
from contextlib import asynccontextmanager
from asyncio import Lock
from fastapi import FastAPI
from logging import getLogger
from pydantic import BaseModel, ConfigDict, PrivateAttr, field_validator
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Dict,
    List,
    Optional,
    Protocol,
    runtime_checkable,
)

from llama_index.core.llms import MessageRole

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
    HumanResponse,
    NewTask,
    TaskDefinition,
    TaskResult,
    ToolCall,
    ToolCallBundle,
    ToolCallResult,
    ServiceDefinition,
    CONTROL_PLANE_NAME,
)
from llama_deploy.tools.utils import get_tool_name_from_service_name
from llama_deploy.utils import get_prompt_params


logger = getLogger(__name__)


HELP_REQUEST_TEMPLATE_STR = (
    "Your assistance is needed. Please respond to the request "
    "provided below:\n===\n\n"
    "{input_str}\n\n===\n"
)


@runtime_checkable
class HumanInputFn(Protocol):
    """Protocol for getting human input."""

    def __call__(self, prompt: str, task_id: str, **kwargs: Any) -> Awaitable[str]:
        ...


async def default_human_input_fn(prompt: str, task_id: str, **kwargs: Any) -> str:
    del task_id
    return input(prompt)


class HumanService(BaseService):
    """A human service for providing human-in-the-loop assistance.

    When launched locally, it will prompt the user for input, which is blocking!

    When launched as a server, it will provide an API for creating and handling tasks.

    Exposes the following endpoints:
    - GET `/`: Get the service information.
    - POST `/process_message`: Process a message.
    - POST `/tasks`: Create a task.
    - GET `/tasks`: Get all tasks.
    - GET `/tasks/{task_id}`: Get a task.
    - POST `/tasks/{task_id}/handle`: Handle a task.

    Attributes:
        service_name (str): The name of the service.
        description (str): The description of the service.
        running (bool): Whether the service is running.
        step_interval (float): The interval in seconds to poll for tool call results. Defaults to 0.1s.
        host (Optional[str]): The host of the service.
        port (Optional[int]): The port of the service.


    """

    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)
    service_name: str
    description: str = "Local Human Service."
    running: bool = True
    step_interval: float = 0.1
    fn_input: HumanInputFn = default_human_input_fn
    human_input_prompt: str = (
        HELP_REQUEST_TEMPLATE_STR  # TODO: use PromptMixin, PromptTemplate
    )
    host: Optional[str] = None
    port: Optional[int] = None

    _outstanding_human_tasks: List["HumanTask"] = PrivateAttr()
    _message_queue: BaseMessageQueue = PrivateAttr()
    _app: FastAPI = PrivateAttr()
    _publisher_id: str = PrivateAttr()
    _publish_callback: Optional[PublishCallback] = PrivateAttr()
    _lock: Lock = PrivateAttr()
    _tasks_as_tool_calls: Dict[str, ToolCall] = PrivateAttr()

    def __init__(
        self,
        message_queue: BaseMessageQueue,
        running: bool = True,
        description: str = "Local Human Service",
        service_name: str = "default_human_service",
        publish_callback: Optional[PublishCallback] = None,
        step_interval: float = 0.1,
        fn_input: HumanInputFn = default_human_input_fn,
        human_input_prompt: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> None:
        human_input_prompt = human_input_prompt or HELP_REQUEST_TEMPLATE_STR
        super().__init__(
            running=running,
            description=description,
            service_name=service_name,
            step_interval=step_interval,
            fn_input=fn_input,
            human_input_prompt=human_input_prompt,
            host=host,
            port=port,
        )

        self._outstanding_human_tasks = []
        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback
        self._lock = asyncio.Lock()
        self._tasks_as_tool_calls = {}
        self._app = FastAPI(lifespan=self.lifespan)

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
        """Get the service definition."""
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

    @property
    def tool_name(self) -> str:
        """The name reserved when this service is used as a tool."""
        return get_tool_name_from_service_name(self.service_name)

    async def processing_loop(self) -> None:
        """The processing loop for the service."""
        logger.info("Processing initiated.")
        while True:
            if not self.running:
                await asyncio.sleep(self.step_interval)
                continue

            async with self.lock:
                try:
                    human_task = self._outstanding_human_tasks.pop(0)
                    task_def = human_task.task_def
                    tool_call = human_task.tool_call
                except IndexError:
                    await asyncio.sleep(self.step_interval)
                    continue

                logger.info(
                    f"Processing request for human help for task: {task_def.task_id}"
                )

                # process req
                prompt = (
                    self.human_input_prompt.format(input_str=task_def.input)
                    if self.human_input_prompt
                    else task_def.input
                )
                result = await self.fn_input(prompt=prompt, task_id=task_def.task_id)

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

                if tool_call:
                    await self.publish(
                        QueueMessage(
                            type=tool_call.source_id,
                            action=ActionTypes.COMPLETED_TOOL_CALL,
                            data=ToolCallResult(
                                id_=tool_call.id_,
                                tool_message=ChatMessage(
                                    content=result,
                                    role=MessageRole.TOOL,
                                    additional_kwargs={
                                        "name": tool_call.tool_call_bundle.tool_name,
                                        "tool_call_id": tool_call.id_,
                                    },
                                ),
                                result=result,
                            ).model_dump(),
                        )
                    )
                else:
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

    class HumanTask(BaseModel):
        """Container for Tasks to be completed by HumanService."""

        task_def: TaskDefinition
        tool_call: Optional[ToolCall] = None

    async def process_message(self, message: QueueMessage) -> None:
        """Process a message received from the message queue."""
        if message.action == ActionTypes.NEW_TASK:
            new_task = NewTask(**message.data or {})
            task_def = new_task.task
            human_task = self.HumanTask(task_def=task_def)
            logger.info(f"Created new task: {task_def.task_id}")
        elif message.action == ActionTypes.NEW_TOOL_CALL:
            task_def = TaskDefinition(**message.data or {})
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
            human_task = self.HumanTask(task_def=task_def, tool_call=task_as_tool_call)
            logger.info(f"Created new tool call as task: {task_def.task_id}")
        else:
            raise ValueError(f"Unhandled action: {message.action}")
        async with self.lock:
            self._outstanding_human_tasks.append(human_task)

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
        """Get general service information."""
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
        """Create a task for the human service."""
        async with self.lock:
            human_task = self.HumanTask(task_def=task)
            self._outstanding_human_tasks.append(human_task)
        return {"task_id": task.task_id}

    async def get_tasks(self) -> List[TaskDefinition]:
        """Get all outstanding tasks."""
        async with self.lock:
            return [ht.task_def for ht in self._outstanding_human_tasks]

    async def get_task(self, task_id: str) -> Optional[TaskDefinition]:
        """Get a specific task by ID."""
        async with self.lock:
            for human_task in self._outstanding_human_tasks:
                if human_task.task_def.task_id == task_id:
                    return human_task.task_def
        return None

    async def handle_task(self, task_id: str, result: HumanResponse) -> None:
        """Handle a task by providing a result."""
        async with self.lock:
            for human_task in self._outstanding_human_tasks:
                task_def = human_task.task_def
                if task_def.task_id == task_id:
                    self._outstanding_human_tasks.remove(human_task)
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
        """Launch the service as a FastAPI server."""
        logger.info(
            f"Lanching server for {self.service_name} at {self.host}:{self.port}"
        )

        class CustomServer(uvicorn.Server):
            def install_signal_handlers(self) -> None:
                pass

        cfg = uvicorn.Config(self._app, host=self.host, port=self.port)
        server = CustomServer(cfg)
        await server.serve()

    @field_validator("human_input_prompt")
    @classmethod
    def validate_human_input_prompt(cls, v: str) -> str:
        """Check if `input_str` is a prompt key."""
        prompt_params = get_prompt_params(v)
        if "input_str" not in prompt_params:
            raise ValueError(
                "`input_str` should be the only param in the prompt template."
            )
        return v


HumanService.model_rebuild()
