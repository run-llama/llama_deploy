import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from typing import Any, AsyncGenerator, Dict, List, Literal, Optional

from llama_index.core.agent import AgentRunner
from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.llms import ChatMessage

from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.message_consumers.callable import CallableMessageConsumer
from agentfile.message_queues.base import BaseMessageQueue
from agentfile.messages.base import QueueMessage
from agentfile.services.base import BaseService
from agentfile.services.types import _ChatMessage
from agentfile.types import (
    ActionTypes,
    TaskResult,
    TaskDefinition,
    ServiceDefinition,
    CONTROL_PLANE_NAME,
)


class AgentService(BaseService):
    service_name: str
    message_queue: BaseMessageQueue
    agent: AgentRunner
    description: str = "Local Agent Service."
    prompt: Optional[List[ChatMessage]] = None
    running: bool = True
    step_interval: float = 0.1

    _app: FastAPI = PrivateAttr()

    def __init__(
        self,
        agent: AgentRunner,
        message_queue: BaseMessageQueue,
        running: bool = True,
        description: str = "Agent Server",
        service_name: str = "default_agent",
        prompt: Optional[List[ChatMessage]] = None,
        step_interval: float = 0.1,
    ) -> None:
        super().__init__(
            agent=agent,
            message_queue=message_queue,
            running=running,
            description=description,
            service_name=service_name,
            step_interval=step_interval,
            prompt=prompt,
        )

        self._app = FastAPI(lifespan=self.lifespan)

        self._app.add_api_route("/", self.home, methods=["GET"], tags=["Agent State"])

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
        return ServiceDefinition(
            service_name=self.service_name,
            description=self.description,
            prompt=self.prompt or [],
        )

    async def processing_loop(self) -> None:
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
                    # finalize the response
                    response = self.agent.finalize_response(
                        task_id, step_output=step_output
                    )

                    # get the latest history
                    history = self.agent.memory.get()

                    # publish the completed task
                    await self.publish(
                        QueueMessage(
                            type=CONTROL_PLANE_NAME,
                            action=ActionTypes.COMPLETED_TASK,
                            data=TaskResult(
                                task_id=task_id,
                                history=history,
                                result=response.response,
                            ).dict(),
                        )
                    )

            await asyncio.sleep(self.step_interval)

    async def process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        if message.action == ActionTypes.NEW_TASK:
            task_def = TaskDefinition(**message.data or {})
            self.agent.create_task(task_def.input, task_id=task_def.task_id)
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

    async def create_task(self, task: TaskDefinition) -> Dict[str, str]:
        task_id = self.agent.create_task(task, task_id=task.task_id)
        return {"task_id": task_id}

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

    async def launch_server(self) -> None:
        uvicorn.run(self._app)
