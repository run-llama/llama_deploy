import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from typing import AsyncGenerator, Dict, List, Literal

from agentfile.schema import _Task, _TaskSate, _TaskStep, _TaskStepOutput, _ChatMessage
from llama_index.core.agent import AgentRunner

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)


class AgentServer:
    def __init__(
        self,
        agent: AgentRunner,
        running: bool = True,
        description: str = "Agent Server",
        step_interval: float = 0.1,
    ):
        self.agent = agent
        self.description = description
        self.running = running
        self.step_interval = step_interval

        self.app = FastAPI(lifespan=self.lifespan)

        self.app.add_api_route("/", self.home, methods=["GET"], tags=["Agent State"])

        self.app.add_api_route(
            "/task", self.create_task, methods=["POST"], tags=["Tasks"]
        )
        self.app.add_api_route(
            "/tasks", self.get_tasks, methods=["GET"], tags=["Tasks"]
        )
        self.app.add_api_route(
            "/tasks/{task_id}", self.get_task, methods=["GET"], tags=["Tasks"]
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

    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncGenerator[None, None]:
        logger.info("Starting up")
        asyncio.create_task(self.processing_loop())
        yield
        logger.info("Shutting down")

    def launch(self) -> None:
        uvicorn.run(self.app)

    async def home(self) -> Dict[str, str]:
        return {
            "agent_description": str(self.description),
            "running": str(self.running),
            "step_interval": f"{self.step_interval} seconds",
            "num_tasks": str(len(self.agent.list_tasks())),
            "num_completed_tasks": str(len(self.agent.get_completed_tasks())),
        }

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
                    self.agent.finalize_response(task_id, step_output=step_output)

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

    async def get_task(self, task_id: str) -> _TaskSate:
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


if __name__ == "__main__":
    from llama_index.core import VectorStoreIndex, Document

    index = VectorStoreIndex.from_documents([Document.example()])
    agent = index.as_chat_engine()

    server = AgentServer(agent)
    server.launch()
