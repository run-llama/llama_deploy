import uuid
import uvicorn
from fastapi import FastAPI
from typing import Any, Callable, Dict, List, Optional

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.llms import LLM
from llama_index.core.objects import ObjectIndex, SimpleObjectNodeMapping
from llama_index.core.storage.kvstore.types import BaseKVStore
from llama_index.core.storage.kvstore import SimpleKVStore
from llama_index.core.selectors import PydanticMultiSelector
from llama_index.core.settings import Settings
from llama_index.core.tools import ToolMetadata
from llama_index.core.vector_stores.types import BasePydanticVectorStore

from agentfile.control_plane.base import BaseControlPlane
from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.message_queues.base import BaseMessageQueue, PublishCallback
from agentfile.messages.base import QueueMessage
from agentfile.types import (
    ActionTypes,
    ServiceDefinition,
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
        llm: Optional[LLM] = None,
        vector_store: Optional[BasePydanticVectorStore] = None,
        publish_callback: Optional[PublishCallback] = None,
        state_store: Optional[BaseKVStore] = None,
        services_store_key: str = "services",
        flows_store_key: str = "flows",
        active_flows_store_key: str = "active_flows",
        tasks_store_key: str = "tasks",
        step_interval: float = 0.1,
        running: bool = True,
    ) -> None:
        self.llm = llm or Settings.llm
        self.object_index = ObjectIndex(
            VectorStoreIndex(
                nodes=[],
                storage_context=StorageContext.from_defaults(vector_store=vector_store),
            ),
            SimpleObjectNodeMapping(),
        )
        self.step_interval = step_interval
        self.running = running

        self.state_store = state_store or SimpleKVStore()
        # TODO: should we store services in a tool retriever?
        self.services_store_key = services_store_key
        self.flows_store_key = flows_store_key
        self.active_flows_store_key = active_flows_store_key
        self.tasks_store_key = tasks_store_key

        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback

        self.app = FastAPI()
        self.app.add_api_route("/", self.home, methods=["GET"], tags=["Control Plane"])

        self.app.add_api_route(
            "/services/register",
            self.register_service,
            methods=["POST"],
            tags=["Services"],
        )
        self.app.add_api_route(
            "/services/deregister",
            self.deregister_service,
            methods=["POST"],
            tags=["Services"],
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

    @property
    def message_queue(self) -> BaseMessageQueue:
        return self._message_queue

    @property
    def publisher_id(self) -> str:
        return self._publisher_id

    @property
    def publish_callback(self) -> Optional[PublishCallback]:
        return self._publish_callback

    def as_consumer(self) -> BaseMessageQueueConsumer:
        return ControlPlaneMessageConsumer(
            message_handler={
                ActionTypes.NEW_TASK: self.create_task,
                ActionTypes.COMPLETED_TASK: self.handle_service_completion,
            }
        )

    def launch(self) -> None:
        uvicorn.run(self.app)

    async def home(self) -> Dict[str, str]:
        return {
            "running": str(self.running),
            "step_interval": str(self.step_interval),
            "services_store_key": self.services_store_key,
            "flows_store_key": self.flows_store_key,
            "active_flows_store_key": self.active_flows_store_key,
        }

    async def register_service(self, service_def: ServiceDefinition) -> None:
        await self.state_store.aput(
            service_def.service_name,
            service_def.dict(),
            collection=self.services_store_key,
        )
        # TODO: currently blocking, should be async
        self.object_index.insert_object(service_def.dict())

    async def deregister_service(self, service_name: str) -> None:
        await self.state_store.adelete(service_name, collection=self.services_store_key)
        # object index does not have delete yet

    async def register_flow(self, flow_def: FlowDefinition) -> None:
        await self.state_store.aput(
            flow_def.flow_id, flow_def.dict(), collection=self.flows_store_key
        )

    async def deregister_flow(self, flow_id: str) -> None:
        await self.state_store.adelete(flow_id, collection=self.flows_store_key)

    async def create_task(self, task_def: TaskDefinition) -> None:
        await self.state_store.aput(
            task_def.task_id, task_def.dict(), collection=self.tasks_store_key
        )

        await self.send_task_to_service(task_def)

    async def get_task_state(self, task_id: str) -> TaskDefinition:
        state_dict = await self.state_store.aget(
            task_id, collection=self.tasks_store_key
        )
        if state_dict is None:
            raise ValueError(f"Task with id {task_id} not found")

        return TaskDefinition.parse_obj(state_dict)

    async def get_all_tasks(self) -> Dict[str, TaskDefinition]:
        state_dicts = await self.state_store.aget_all(collection=self.tasks_store_key)
        return {
            task_id: TaskDefinition.parse_obj(state_dict)
            for task_id, state_dict in state_dicts.items()
        }

    async def send_task_to_service(self, task_def: TaskDefinition) -> None:
        service_retriever = self.object_index.as_retriever(similarity_top_k=5)

        # could also route based on similarity alone.
        # TODO: Figure out user-specified routing
        service_def_dicts: List[dict] = await service_retriever.aretrieve(
            task_def.input
        )
        service_defs = [
            ServiceDefinition.parse_obj(service_def_dict)
            for service_def_dict in service_def_dicts
        ]
        if len(service_defs) > 1:
            selector = PydanticMultiSelector.from_defaults(
                llm=self.llm,
            )
            service_def_metadata = [
                ToolMetadata(
                    description=service_def.description,
                    name=service_def.service_name,
                )
                for service_def in service_defs
            ]
            result = await selector.aselect(service_def_metadata, task_def.input)

            selected_service_name = service_defs[result.inds[0]].service_name
        else:
            selected_service_name = service_defs[0].service_name

        await self.publish(
            QueueMessage(
                type=selected_service_name,
                data=task_def.dict(),
                action=ActionTypes.NEW_TASK,
            ),
        )

    async def handle_service_completion(
        self,
        task_result: TaskResult,
    ) -> None:
        # TODO: figure out how to route to the next service
        await self.publish(
            QueueMessage(
                type="human",
                action=ActionTypes.COMPLETED_TASK,
                data=task_result.result,
            )
        )

    async def get_next_service(self, task_id: str) -> str:
        return ""

    async def request_user_input(self, task_id: str, message: str) -> None:
        pass

    async def handle_user_input(self, task_id: str, user_input: str) -> None:
        pass
