import uvicorn
from fastapi import FastAPI
from typing import Any, Callable, Dict, Optional

from llama_index.core.storage.kvstore.types import BaseKVStore
from llama_index.core.storage.kvstore import SimpleKVStore

from agentfile.control_plane.base import BaseControlPlane
from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.message_queues.base import BaseMessageQueue
from agentfile.messages.base import QueueMessage
from agentfile.types import (
    ActionTypes,
    AgentDefinition,
    FlowDefinition,
    TaskDefinition,
    TaskResult,
)

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)


class ControlPlaneMessageConsumer(BaseMessageQueueConsumer):
    message_handler: Dict[str, Callable]
    message_type: str = "control_plane"

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        action = message.action
        if action not in self.message_handler:
            raise ValueError(f"Action {action} not supported by control plane")

        if action == ActionTypes.NEW_TASK and message.data is not None:
            await self.message_handler[action](TaskDefinition(**message.data))
        elif action == ActionTypes.COMPLETED_TASK and message.data is not None:
            await self.message_handler[action](TaskResult(**message.data))


class FastAPIControlPlane(BaseControlPlane):
    def __init__(
        self,
        message_queue: BaseMessageQueue,
        state_store: Optional[BaseKVStore] = None,
        agents_store_key: str = "agents",
        flows_store_key: str = "flows",
        active_flows_store_key: str = "active_flows",
        tasks_store_key: str = "tasks",
        step_interval: float = 0.1,
        running: bool = True,
    ) -> None:
        self.step_interval = step_interval
        self.running = running

        self.state_store = state_store or SimpleKVStore()
        # TODO: should we store agents in a tool retriever?
        self.agents_store_key = agents_store_key
        self.flows_store_key = flows_store_key
        self.active_flows_store_key = active_flows_store_key
        self.tasks_store_key = tasks_store_key

        self.message_queue = message_queue

        self.app = FastAPI()
        self.app.add_api_route("/", self.home, methods=["GET"], tags=["Control Plane"])

        self.app.add_api_route(
            "/agents/register", self.register_agent, methods=["POST"], tags=["Agents"]
        )
        self.app.add_api_route(
            "/agents/deregister",
            self.deregister_agent,
            methods=["POST"],
            tags=["Agents"],
        )

        self.app.add_api_route(
            "/flows/register", self.register_flow, methods=["POST"], tags=["Flows"]
        )
        self.app.add_api_route(
            "/flows/deregister", self.deregister_flow, methods=["POST"], tags=["Flows"]
        )

        self.app.add_api_route(
            "/tasks", self.create_task, methods=["POST"], tags=["Tasks"]
        )
        self.app.add_api_route(
            "/tasks/{task_id}", self.get_task_state, methods=["GET"], tags=["Tasks"]
        )

    def get_consumer(self) -> BaseMessageQueueConsumer:
        return ControlPlaneMessageConsumer(
            message_handler={
                ActionTypes.NEW_TASK: self.create_task,
                ActionTypes.COMPLETED_TASK: self.handle_agent_completion,
            }
        )

    def launch(self) -> None:
        uvicorn.run(self.app)

    async def home(self) -> Dict[str, str]:
        return {
            "running": str(self.running),
            "step_interval": str(self.step_interval),
            "agents_store_key": self.agents_store_key,
            "flows_store_key": self.flows_store_key,
            "active_flows_store_key": self.active_flows_store_key,
        }

    async def register_agent(self, agent_def: AgentDefinition) -> None:
        await self.state_store.aput(
            agent_def.agent_id, agent_def.model_dump(), collection=self.agents_store_key
        )

    async def deregister_agent(self, agent_id: str) -> None:
        await self.state_store.adelete(agent_id, collection=self.agents_store_key)

    async def register_flow(self, flow_def: FlowDefinition) -> None:
        await self.state_store.aput(
            flow_def.flow_id, flow_def.model_dump(), collection=self.flows_store_key
        )

    async def deregister_flow(self, flow_id: str) -> None:
        await self.state_store.adelete(flow_id, collection=self.flows_store_key)

    async def create_task(self, task_def: TaskDefinition) -> None:
        # TODO: route task to flows or agent?
        # Right now assumes task def contains destination agent_id
        await self.state_store.aput(
            task_def.task_id, task_def.model_dump(), collection=self.tasks_store_key
        )

        await self.send_task_to_agent(task_def)

    async def get_task_state(self, task_id: str) -> TaskDefinition:
        state_dict = await self.state_store.aget(
            task_id, collection=self.tasks_store_key
        )
        if state_dict is None:
            raise ValueError(f"Task with id {task_id} not found")

        return TaskDefinition.model_validate(state_dict)

    async def get_all_tasks(self) -> Dict[str, TaskDefinition]:
        state_dicts = await self.state_store.aget_all(collection=self.tasks_store_key)
        return {
            task_id: TaskDefinition.model_validate(state_dict)
            for task_id, state_dict in state_dicts.items()
        }

    async def send_task_to_agent(self, task_def: TaskDefinition) -> None:
        all_agents = await self.state_store.aget_all(collection=self.agents_store_key)
        agent_id = task_def.agent_id or list(all_agents.keys())[0]

        await self.message_queue.publish(
            QueueMessage(
                source_id=self.id_,
                type=agent_id,
                data=task_def.model_dump(),
                action=ActionTypes.NEW_TASK,
            )
        )

    async def handle_agent_completion(
        self,
        task_result: TaskResult,
    ) -> None:
        # TODO: figure out logic for deciding what to do next
        # by default, assume done (return to user?)
        await self.state_store.adelete(
            task_result.task_id, collection=self.tasks_store_key
        )

        await self.message_queue.publish(
            QueueMessage(
                source_id=self.id_,
                type="human",
                action=ActionTypes.COMPLETED_TASK,
                data=task_result.result,
            )
        )

    async def get_next_agent(self, task_id: str) -> str:
        return ""

    async def request_user_input(self, task_id: str, message: str) -> None:
        pass

    async def handle_user_input(self, task_id: str, user_input: str) -> None:
        pass
