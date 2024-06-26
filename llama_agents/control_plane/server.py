import copy
import uuid
import uvicorn
from fastapi import FastAPI
from logging import getLogger
from typing import Dict, List, Optional

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.objects import ObjectIndex, SimpleObjectNodeMapping
from llama_index.core.storage.kvstore.types import BaseKVStore
from llama_index.core.storage.kvstore import SimpleKVStore
from llama_index.core.vector_stores.types import BasePydanticVectorStore

from llama_agents.control_plane.base import BaseControlPlane
from llama_agents.message_consumers.base import BaseMessageQueueConsumer
from llama_agents.message_consumers.callable import CallableMessageConsumer
from llama_agents.message_consumers.remote import RemoteMessageConsumer
from llama_agents.message_queues.base import BaseMessageQueue, PublishCallback
from llama_agents.messages.base import QueueMessage
from llama_agents.orchestrators.base import BaseOrchestrator
from llama_agents.tools import ServiceTool
from llama_agents.types import (
    ActionTypes,
    ServiceDefinition,
    TaskDefinition,
    TaskResult,
)

logger = getLogger(__name__)


class ControlPlaneServer(BaseControlPlane):
    def __init__(
        self,
        message_queue: BaseMessageQueue,
        orchestrator: BaseOrchestrator,
        vector_store: Optional[BasePydanticVectorStore] = None,
        publish_callback: Optional[PublishCallback] = None,
        state_store: Optional[BaseKVStore] = None,
        services_store_key: str = "services",
        tasks_store_key: str = "tasks",
        step_interval: float = 0.1,
        services_retrieval_threshold: int = 5,
        host: str = "127.0.0.1",
        port: int = 8000,
        running: bool = True,
    ) -> None:
        self.orchestrator = orchestrator
        self.object_index = ObjectIndex(
            VectorStoreIndex(
                nodes=[],
                storage_context=StorageContext.from_defaults(vector_store=vector_store),
            ),
            SimpleObjectNodeMapping(),
        )
        self.step_interval = step_interval
        self.running = running
        self.host = host
        self.port = port

        self.state_store = state_store or SimpleKVStore()

        # TODO: should we store services in a tool retriever?
        self.services_store_key = services_store_key
        self.tasks_store_key = tasks_store_key

        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback

        self._services_cache: Dict[str, ServiceDefinition] = {}
        self._total_services = 0
        self._services_retrieval_threshold = services_retrieval_threshold

        self.app = FastAPI()
        self.app.add_api_route("/", self.home, methods=["GET"], tags=["Control Plane"])
        self.app.add_api_route(
            "/process_message",
            self.process_message,
            methods=["POST"],
            tags=["Control Plane"],
        )

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
            "/services/{service_name}",
            self.get_service,
            methods=["GET"],
            tags=["Services"],
        )
        self.app.add_api_route(
            "/services",
            self.get_all_services,
            methods=["GET"],
            tags=["Services"],
        )

        self.app.add_api_route(
            "/tasks", self.create_task, methods=["POST"], tags=["Tasks"]
        )
        self.app.add_api_route(
            "/tasks", self.get_all_tasks, methods=["GET"], tags=["Tasks"]
        )
        self.app.add_api_route(
            "/tasks/{task_id}",
            self.get_task_state_api_safe,
            methods=["GET"],
            tags=["Tasks"],
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

    async def process_message(self, message: QueueMessage) -> None:
        action = message.action

        if action == ActionTypes.NEW_TASK and message.data is not None:
            await self.create_task(TaskDefinition(**message.data))
        elif action == ActionTypes.COMPLETED_TASK and message.data is not None:
            await self.handle_service_completion(TaskResult(**message.data))
        else:
            raise ValueError(f"Action {action} not supported by control plane")

    def as_consumer(self, remote: bool = False) -> BaseMessageQueueConsumer:
        if remote:
            return RemoteMessageConsumer(
                id_=self.publisher_id,
                url=f"http://{self.host}:{self.port}/process_message",
                message_type="control_plane",
            )

        return CallableMessageConsumer(
            id_=self.publisher_id,
            message_type="control_plane",
            handler=self.process_message,
        )

    async def launch_server(self) -> None:
        logger.info(f"Launching control plane server at {self.host}:{self.port}")
        # uvicorn.run(self.app, host=self.host, port=self.port)

        class CustomServer(uvicorn.Server):
            def install_signal_handlers(self) -> None:
                pass

        cfg = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = CustomServer(cfg)
        await server.serve()

    async def home(self) -> Dict[str, str]:
        return {
            "running": str(self.running),
            "step_interval": str(self.step_interval),
            "services_store_key": self.services_store_key,
            "total_services": str(self._total_services),
            "services_retrieval_threshold": str(self._services_retrieval_threshold),
        }

    async def register_service(self, service_def: ServiceDefinition) -> None:
        await self.state_store.aput(
            service_def.service_name,
            service_def.model_dump(),
            collection=self.services_store_key,
        )

        # decide to use cache vs. retrieval
        self._total_services += 1
        if self._total_services > self._services_retrieval_threshold:
            # TODO: currently blocking, should be async
            self.object_index.insert_object(service_def.model_dump())
            for service in self._services_cache.values():
                self.object_index.insert_object(service.model_dump())
            self._services_cache = {}
        else:
            self._services_cache[service_def.service_name] = service_def

    async def deregister_service(self, service_name: str) -> None:
        deleted = await self.state_store.adelete(
            service_name, collection=self.services_store_key
        )
        if service_name in self._services_cache:
            del self._services_cache[service_name]

        if deleted:
            self._total_services -= 1
        # TODO: object index does not have delete yet

    async def get_service(self, service_name: str) -> ServiceDefinition:
        service_dict = await self.state_store.aget(
            service_name, collection=self.services_store_key
        )
        if service_dict is None:
            raise ValueError(f"Service with name {service_name} not found")

        return ServiceDefinition.model_validate(service_dict)

    async def get_all_services(self) -> Dict[str, ServiceDefinition]:
        service_dicts = await self.state_store.aget_all(
            collection=self.services_store_key
        )
        return {
            service_name: ServiceDefinition.model_validate(service_dict)
            for service_name, service_dict in service_dicts.items()
        }

    async def create_task(self, task_def: TaskDefinition) -> Dict[str, str]:
        await self.state_store.aput(
            task_def.task_id, task_def.model_dump(), collection=self.tasks_store_key
        )

        task_def = await self.send_task_to_service(task_def)
        await self.state_store.aput(
            task_def.task_id, task_def.model_dump(), collection=self.tasks_store_key
        )
        logger.debug(f"Task {task_def.task_id} created")
        return {"task_id": task_def.task_id}

    async def send_task_to_service(self, task_def: TaskDefinition) -> TaskDefinition:
        if self._total_services > self._services_retrieval_threshold:
            service_retriever = self.object_index.as_retriever(similarity_top_k=5)

            # could also route based on similarity alone.
            # TODO: Figure out user-specified routing
            service_def_dicts: List[dict] = await service_retriever.aretrieve(
                task_def.input
            )
            service_defs = [
                ServiceDefinition.model_validate(service_def_dict)
                for service_def_dict in service_def_dicts
            ]
        else:
            service_defs = list(self._services_cache.values())

        service_tools = [
            ServiceTool.from_service_definition(service_def)
            for service_def in service_defs
        ]

        next_messages, task_state = await self.orchestrator.get_next_messages(
            task_def, service_tools, task_def.state
        )

        logger.debug(f"Sending task {task_def.task_id} to services: {next_messages}")

        for message in next_messages:
            await self.publish(message)

        task_def.state.update(task_state)
        return task_def

    async def handle_service_completion(
        self,
        task_result: TaskResult,
    ) -> None:
        # add result to task state
        task_def = await self.get_task_state(task_result.task_id)
        state = await self.orchestrator.add_result_to_state(task_result, task_def.state)
        task_def.state.update(state)

        # generate and send new tasks (if any)
        task_def = await self.send_task_to_service(task_def)

        await self.state_store.aput(
            task_def.task_id, task_def.model_dump(), collection=self.tasks_store_key
        )

    async def get_task_state(self, task_id: str) -> TaskDefinition:
        state_dict = await self.state_store.aget(
            task_id, collection=self.tasks_store_key
        )
        if state_dict is None:
            raise ValueError(f"Task with id {task_id} not found")

        return TaskDefinition(**state_dict)

    async def get_task_state_api_safe(self, task_id: str) -> TaskDefinition:
        state_dict = await self.state_store.aget(
            task_id, collection=self.tasks_store_key
        )
        state_dict = copy.deepcopy(state_dict)

        if state_dict is None:
            raise ValueError(f"Task with id {task_id} not found")

        # remove an bytes objects from state
        for key, val in state_dict["state"].items():
            if isinstance(val, bytes):
                state_dict["state"][key] = "<bytes object>"

        return TaskDefinition(**state_dict)

    async def get_all_tasks(self) -> Dict[str, TaskDefinition]:
        state_dicts = await self.state_store.aget_all(collection=self.tasks_store_key)
        state_dicts = copy.deepcopy(state_dicts)

        task_defs = {}
        for task_id, state_dict in state_dicts.items():
            # remove an bytes objects from state
            for key, val in state_dict["state"].items():
                if isinstance(val, bytes):
                    state_dict["state"][key] = "<bytes object>"
            task_defs[task_id] = TaskDefinition(**state_dict)

        return task_defs


if __name__ == "__main__":
    from llama_agents import SimpleMessageQueue, AgentOrchestrator
    from llama_index.llms.openai import OpenAI

    control_plane = ControlPlaneServer(
        SimpleMessageQueue(), AgentOrchestrator(llm=OpenAI())
    )
    import asyncio

    asyncio.run(control_plane.launch_server())
