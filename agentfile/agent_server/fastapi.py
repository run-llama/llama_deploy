import asyncio
import uuid
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from typing import Any, AsyncGenerator, Callable, Dict, List, Literal, Optional

from agentfile.agent_server.base import BaseAgentServer
from agentfile.agent_server.types import (
    _Task,
    _TaskSate,
    _TaskStep,
    _TaskStepOutput,
    _ChatMessage,
)
from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.message_queues.base import BaseMessageQueue, PublishCallback
from agentfile.messages.base import QueueMessage
from agentfile.types import ActionTypes, TaskResult, AgentDefinition
from llama_index.core.agent import AgentRunner

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)


class AgentMessageConsumer(BaseMessageQueueConsumer):
    message_handler: Dict[str, Callable]
    message_type: str = "default_agent"

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        action = message.action
        if action not in self.message_handler:
            raise ValueError(f"Action {action} not supported by control plane")

        if (
            action == ActionTypes.NEW_TASK
            and isinstance(message.data, dict)
            and "input" in message.data
        ):
            await self.message_handler[action](message.data["input"])


class FastAPIAgentServer(BaseAgentServer):
    def __init__(
        self,
        agent: AgentRunner,
        message_queue: BaseMessageQueue,
        running: bool = True,
        description: str = "Agent Server",
        agent_id: str = "default_agent",
        agent_definition: Optional[AgentDefinition] = None,
        publish_callback: Optional[PublishCallback] = None,
        step_interval: float = 0.1,
    ) -> None:
        self._agent_definition = agent_definition or AgentDefinition(
            agent_id=agent_id, description=description
        )
        self.agent = agent
        self.description = description
        self.running = running
        self.step_interval = step_interval
        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback

        self.app = FastAPI(lifespan=self.lifespan)

        self.app.add_api_route("/", self.home, methods=["GET"], tags=["Agent State"])

        self.app.add_api_route(
            "/task", self.create_task, methods=["POST"], tags=["Tasks"]
        )
        self.app.add_api_route(
            "/tasks", self.get_tasks, methods=["GET"], tags=["Tasks"]
        )
        self.app.add_api_route(
            "/tasks/{task_id}", self.get_task_state, methods=["GET"], tags=["Tasks"]
        )
        self.app.add_api_route(
            "/completed_tasks",
            self.get_completed_tasks,
            methods=["GET"],
            tags=["Tasks"],
        )
        self.app.add_api_route(
            "/tasks/{task_id}/output",
            self.get_task_output,
            methods=["GET"],
            tags=["Tasks"],
        )
        self.app.add_api_route(
            "/tasks/{task_id}/steps",
            self.get_task_steps,
            methods=["GET"],
            tags=["Tasks"],
        )
        self.app.add_api_route(
            "/tasks/{task_id}/completed_steps",
            self.get_completed_steps,
            methods=["GET"],
            tags=["Tasks"],
        )

        self.app.add_api_route(
            "/description", self.get_description, methods=["GET"], tags=["Agent State"]
        )
        self.app.add_api_route(
            "/messages", self.get_messages, methods=["GET"], tags=["Agent State"]
        )
        self.app.add_api_route(
            "/toggle_agent_running",
            self.toggle_agent_running,
            methods=["POST"],
            tags=["Agent State"],
        )
        self.app.add_api_route(
            "/is_worker_running",
            self.is_worker_running,
            methods=["GET"],
            tags=["Agent State"],
        )
        self.app.add_api_route(
            "/reset_agent", self.reset_agent, methods=["POST"], tags=["Agent State"]
        )

    @property
    def agent_definition(self) -> AgentDefinition:
        return self._agent_definition

    @property
    def message_queue(self) -> BaseMessageQueue:
        return self._message_queue

    @property
    def publisher_id(self) -> str:
        return self._publisher_id

    @property
    def publish_callback(self) -> Optional[PublishCallback]:
        return self._publish_callback

    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncGenerator[None, None]:
        logger.info("Starting up")
        asyncio.create_task(self.start_processing_loop())
        yield
        logger.info("Shutting down")

    def launch(self) -> None:
        uvicorn.run(self.app)

    def get_consumer(self) -> BaseMessageQueueConsumer:
        return AgentMessageConsumer(
            message_type=self.agent_definition.agent_id,
            message_handler={
                ActionTypes.NEW_TASK: self.create_task,
            },
        )

    async def home(self) -> Dict[str, str]:
        return {
            **self.agent_definition.model_dump(),
            "running": str(self.running),
            "step_interval": f"{self.step_interval} seconds",
            "num_tasks": str(len(self.agent.list_tasks())),
            "num_completed_tasks": str(len(self.agent.get_completed_tasks())),
        }

    async def start_processing_loop(self) -> None:
        while True:
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
                    response = self.agent.finalize_response(
                        task_id, step_output=step_output
                    )
                    await self.publish(
                        QueueMessage(
                            publisher_id=self.publisher_id,
                            type="control_plane",
                            action=ActionTypes.COMPLETED_TASK,
                            data=TaskResult(
                                task_id=task_id,
                                result=response.response,
                            ).model_dump(),
                        ),
                        callback=self.publish_callback,
                    )

            await asyncio.sleep(self.step_interval)

    async def get_description(self) -> str:
        return self.description

    async def create_task(self, input: str) -> _Task:
        task = self.agent.create_task(input)

        return _Task.from_task(task)

    async def get_tasks(self) -> List[_Task]:
        tasks = self.agent.list_tasks()

        _tasks = []
        for task in tasks:
            _tasks.append(_Task.from_task(task))

        return _tasks

    async def get_task_state(self, task_id: str) -> _TaskSate:
        task_state = self.agent.state.task_dict.get(task_id)
        if task_state is None:
            raise HTTPException(status_code=404, detail="Task not found")

        return _TaskSate.from_task_state(task_state)

    async def get_completed_tasks(self) -> List[_Task]:
        completed_tasks = self.agent.get_completed_tasks()

        _completed_tasks = []
        for task in completed_tasks:
            _completed_tasks.append(_Task.from_task(task))

        return _completed_tasks

    async def get_task_output(self, task_id: str) -> _TaskStepOutput:
        task_output = self.agent.get_task_output(task_id)

        return _TaskStepOutput.from_task_step_output(task_output)

    async def get_task_steps(self, task_id: str) -> List[_TaskStep]:
        task_steps = self.agent.get_upcoming_steps(task_id)

        steps = []
        for step in task_steps:
            steps.append(_TaskStep.from_task_step(step))

        return steps

    async def get_completed_steps(self, task_id: str) -> List[_TaskStepOutput]:
        completed_step_outputs = self.agent.get_completed_steps(task_id)

        _step_outputs = []
        for step_output in completed_step_outputs:
            _step_outputs.append(_TaskStepOutput.from_task_step_output(step_output))

        return _step_outputs

    # ---- Agent Control ----

    async def get_messages(self) -> List[_ChatMessage]:
        messages = self.agent.chat_history

        return [_ChatMessage.from_chat_message(message) for message in messages]

    async def toggle_agent_running(
        self, state: Literal["running", "stopped"]
    ) -> Dict[str, bool]:
        self.running = state == "running"

        return {"running": self.running}

    async def is_worker_running(self) -> Dict[str, bool]:
        return {"running": self.running}

    async def reset_agent(self) -> Dict[str, str]:
        self.agent.reset()

        return {"message": "Agent reset"}
