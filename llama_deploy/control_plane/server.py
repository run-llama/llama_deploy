import json
import uuid
import uvicorn
from fastapi import FastAPI, HTTPException
from logging import getLogger
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, List, Optional

from llama_index.core.storage.kvstore.types import BaseKVStore
from llama_index.core.storage.kvstore import SimpleKVStore

from llama_deploy.control_plane.base import BaseControlPlane
from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)
from llama_deploy.message_consumers.callable import CallableMessageConsumer
from llama_deploy.message_consumers.remote import RemoteMessageConsumer
from llama_deploy.message_queues.base import BaseMessageQueue, PublishCallback
from llama_deploy.messages.base import QueueMessage
from llama_deploy.orchestrators.base import BaseOrchestrator
from llama_deploy.orchestrators.utils import get_result_key
from llama_deploy.types import (
    ActionTypes,
    SessionDefinition,
    ServiceDefinition,
    TaskDefinition,
    TaskResult,
)

logger = getLogger(__name__)


class ControlPlaneConfig(BaseSettings):
    """Control plane configuration."""

    model_config = SettingsConfigDict(
        env_prefix="CONTROL_PLANE_", arbitrary_types_allowed=True
    )

    state_store: Optional[BaseKVStore] = None
    services_store_key: str = "services"
    tasks_store_key: str = "tasks"
    session_store_key: str = "sessions"
    step_interval: float = 0.1
    host: str = "127.0.0.1"
    port: Optional[int] = 8000
    internal_host: Optional[str] = None
    internal_port: Optional[int] = None
    running: bool = True

    @property
    def url(self) -> str:
        if self.port:
            return f"http://{self.host}:{self.port}"
        else:
            return f"http://{self.host}"


class ControlPlaneServer(BaseControlPlane):
    """Control plane server.

    The control plane is responsible for managing the state of the system, including:
    - Registering services.
    - Submitting tasks.
    - Managing task state.
    - Handling service completion.
    - Launching the control plane server.

    Args:
        message_queue (BaseMessageQueue): Message queue for the system.
        orchestrator (BaseOrchestrator): Orchestrator for the system.
        publish_callback (Optional[PublishCallback], optional): Callback for publishing messages. Defaults to None.
        state_store (Optional[BaseKVStore], optional): State store for the system. Defaults to None.
        services_store_key (str, optional): Key for the services store. Defaults to "services".
        tasks_store_key (str, optional): Key for the tasks store. Defaults to "tasks".
        step_interval (float, optional): The interval in seconds to poll for tool call results. Defaults to 0.1s.
        host (str, optional): The host of the service. Defaults to "127.0.0.1".
        port (Optional[int], optional): The port of the service. Defaults to 8000.
        internal_host (Optional[str], optional): The host for external networking as in Docker-Compose or K8s.
        internal_port (Optional[int], optional): The port for external networking as in Docker-Compose or K8s.
        running (bool, optional): Whether the service is running. Defaults to True.

    Examples:
        ```python
        from llama_deploy import ControlPlaneServer
        from llama_deploy import SimpleMessageQueue, SimpleOrchestrator
        from llama_index.llms.openai import OpenAI

        control_plane = ControlPlaneServer(
            SimpleMessageQueue(),
            SimpleOrchestrator(),
        )
        ```
    """

    def __init__(
        self,
        message_queue: BaseMessageQueue,
        orchestrator: BaseOrchestrator,
        publish_callback: Optional[PublishCallback] = None,
        state_store: Optional[BaseKVStore] = None,
        services_store_key: str = "services",
        tasks_store_key: str = "tasks",
        session_store_key: str = "sessions",
        step_interval: float = 0.1,
        host: str = "127.0.0.1",
        port: Optional[int] = 8000,
        internal_host: Optional[str] = None,
        internal_port: Optional[int] = None,
        running: bool = True,
    ) -> None:
        self.orchestrator = orchestrator

        self.step_interval = step_interval
        self.running = running
        self.host = host
        self.port = port
        self.internal_host = internal_host
        self.internal_port = internal_port

        self.state_store = state_store or SimpleKVStore()

        self.services_store_key = services_store_key
        self.tasks_store_key = tasks_store_key
        self.session_store_key = session_store_key

        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback

        self.app = FastAPI()
        self.app.add_api_route("/", self.home, methods=["GET"], tags=["Control Plane"])
        self.app.add_api_route(
            "/process_message",
            self.process_message,
            methods=["POST"],
            tags=["Control Plane"],
        )
        self.app.add_api_route(
            "/queue_config",
            self.get_message_queue_config,
            methods=["GET"],
            tags=["Message Queue"],
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
            "/sessions/{session_id}",
            self.get_session,
            methods=["GET"],
            tags=["Sessions"],
        )
        self.app.add_api_route(
            "/sessions/create",
            self.create_session,
            methods=["POST"],
            tags=["Sessions"],
        )
        self.app.add_api_route(
            "/sessions/{session_id}/delete",
            self.delete_session,
            methods=["POST"],
            tags=["Sessions"],
        )
        self.app.add_api_route(
            "/sessions/{session_id}/tasks",
            self.add_task_to_session,
            methods=["POST"],
            tags=["Sessions"],
        )
        self.app.add_api_route(
            "/sessions",
            self.get_all_sessions,
            methods=["GET"],
            tags=["Sessions"],
        )
        self.app.add_api_route(
            "/sessions/{session_id}/tasks",
            self.get_session_tasks,
            methods=["GET"],
            tags=["Sessions"],
        )
        self.app.add_api_route(
            "/sessions/{session_id}/current_task",
            self.get_current_task,
            methods=["GET"],
            tags=["Sessions"],
        )
        self.app.add_api_route(
            "/sessions/{session_id}/tasks/{task_id}/result",
            self.get_task_result,
            methods=["GET"],
            tags=["Sessions"],
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
            task_def = TaskDefinition(**message.data)
            if task_def.session_id is None:
                task_def.session_id = await self.create_session()

            await self.add_task_to_session(task_def.session_id, task_def)
        elif action == ActionTypes.COMPLETED_TASK and message.data is not None:
            await self.handle_service_completion(TaskResult(**message.data))
        else:
            raise ValueError(f"Action {action} not supported by control plane")

    def as_consumer(self, remote: bool = False) -> BaseMessageQueueConsumer:
        if remote:
            return RemoteMessageConsumer(
                id_=self.publisher_id,
                url=(
                    f"http://{self.host}:{self.port}/process_message"
                    if self.port
                    else f"http://{self.host}/process_message"
                ),
                message_type="control_plane",
            )

        return CallableMessageConsumer(
            id_=self.publisher_id,
            message_type="control_plane",
            handler=self.process_message,
        )

    async def launch_server(self) -> None:
        # give precedence to external settings
        host = self.internal_host or self.host
        port = self.internal_port or self.port
        logger.info(f"Launching control plane server at {host}:{port}")
        # uvicorn.run(self.app, host=self.host, port=self.port)

        class CustomServer(uvicorn.Server):
            def install_signal_handlers(self) -> None:
                pass

        cfg = uvicorn.Config(self.app, host=host, port=port)
        server = CustomServer(cfg)
        await server.serve()

    async def home(self) -> Dict[str, str]:
        return {
            "running": str(self.running),
            "step_interval": str(self.step_interval),
            "services_store_key": self.services_store_key,
            "tasks_store_key": self.tasks_store_key,
            "session_store_key": self.session_store_key,
        }

    async def register_service(self, service_def: ServiceDefinition) -> None:
        await self.state_store.aput(
            service_def.service_name,
            service_def.model_dump(),
            collection=self.services_store_key,
        )

    async def deregister_service(self, service_name: str) -> None:
        await self.state_store.adelete(service_name, collection=self.services_store_key)

    async def get_service(self, service_name: str) -> ServiceDefinition:
        service_dict = await self.state_store.aget(
            service_name, collection=self.services_store_key
        )
        if service_dict is None:
            raise HTTPException(status_code=404, detail="Service not found")

        return ServiceDefinition.model_validate(service_dict)

    async def get_all_services(self) -> Dict[str, ServiceDefinition]:
        service_dicts = await self.state_store.aget_all(
            collection=self.services_store_key
        )

        return {
            service_name: ServiceDefinition.model_validate(service_dict)
            for service_name, service_dict in service_dicts.items()
        }

    async def create_session(self) -> str:
        session = SessionDefinition()
        await self.state_store.aput(
            session.session_id,
            session.model_dump(),
            collection=self.session_store_key,
        )

        return session.session_id

    async def get_session(self, session_id: str) -> SessionDefinition:
        session_dict = await self.state_store.aget(
            session_id, collection=self.session_store_key
        )
        if session_dict is None:
            raise HTTPException(status_code=404, detail="Session not found")

        return SessionDefinition(**session_dict)

    async def delete_session(self, session_id: str) -> None:
        await self.state_store.adelete(session_id, collection=self.session_store_key)

    async def get_all_sessions(self) -> Dict[str, SessionDefinition]:
        session_dicts = await self.state_store.aget_all(
            collection=self.session_store_key
        )

        return {
            session_id: SessionDefinition(**session_dict)
            for session_id, session_dict in session_dicts.items()
        }

    async def get_session_tasks(self, session_id: str) -> List[TaskDefinition]:
        session = await self.get_session(session_id)
        task_defs = []
        for task_id in session.task_ids:
            task_defs.append(await self.get_task(task_id))
        return task_defs

    async def get_current_task(self, session_id: str) -> Optional[TaskDefinition]:
        session = await self.get_session(session_id)
        if len(session.task_ids) == 0:
            return None
        return await self.get_task(session.task_ids[-1])

    async def add_task_to_session(
        self, session_id: str, task_def: TaskDefinition
    ) -> str:
        session_dict = await self.state_store.aget(
            session_id, collection=self.session_store_key
        )
        if session_dict is None:
            raise HTTPException(status_code=404, detail="Session not found")

        session = SessionDefinition(**session_dict)
        session.task_ids.append(task_def.task_id)
        await self.state_store.aput(
            session_id, session.model_dump(), collection=self.session_store_key
        )

        await self.state_store.aput(
            task_def.task_id, task_def.model_dump(), collection=self.tasks_store_key
        )

        task_def = await self.send_task_to_service(task_def)

        return task_def.task_id

    async def send_task_to_service(self, task_def: TaskDefinition) -> TaskDefinition:
        if task_def.session_id is None:
            raise ValueError(f"Task with id {task_def.task_id} has no session")

        session = await self.get_session(task_def.session_id)

        next_messages, session_state = await self.orchestrator.get_next_messages(
            task_def, session.state
        )

        logger.debug(f"Sending task {task_def.task_id} to services: {next_messages}")

        for message in next_messages:
            await self.publish(message)

        session.state.update(session_state)

        await self.state_store.aput(
            task_def.session_id, session.model_dump(), collection=self.session_store_key
        )

        return task_def

    async def handle_service_completion(
        self,
        task_result: TaskResult,
    ) -> None:
        # add result to task state
        task_def = await self.get_task(task_result.task_id)
        if task_def.session_id is None:
            raise ValueError(f"Task with id {task_result.task_id} has no session")

        session = await self.get_session(task_def.session_id)
        state = await self.orchestrator.add_result_to_state(task_result, session.state)

        # update session state
        session.state.update(state)
        await self.state_store.aput(
            session.session_id,
            session.model_dump(),
            collection=self.session_store_key,
        )

        # generate and send new tasks (if any)
        task_def = await self.send_task_to_service(task_def)

        await self.state_store.aput(
            task_def.task_id, task_def.model_dump(), collection=self.tasks_store_key
        )

    async def get_task(self, task_id: str) -> TaskDefinition:
        state_dict = await self.state_store.aget(
            task_id, collection=self.tasks_store_key
        )
        if state_dict is None:
            raise HTTPException(status_code=404, detail="Task not found")

        return TaskDefinition(**state_dict)

    async def get_task_result(
        self, task_id: str, session_id: str
    ) -> Optional[TaskResult]:
        """Get the result of a task if it has one.

        Args:
            task_id (str): The ID of the task to get the result for.
            session_id (str): The ID of the session the task belongs to.

        Returns:
            Optional[TaskResult]: The result of the task if it has one, otherwise None.
        """
        session = await self.get_session(session_id)

        result_key = get_result_key(task_id)
        if result_key not in session.state:
            return None

        result = session.state[result_key]
        if not isinstance(result, TaskResult):
            if isinstance(result, dict):
                result = TaskResult(**result)
            elif isinstance(result, str):
                result = TaskResult(**json.loads(result))
            else:
                raise HTTPException(status_code=500, detail="Unexpected result type")

        # sanity check
        if result.task_id != task_id:
            logger.debug(
                f"Retrieved result did not match requested task_id: {str(result)}"
            )
            return None

        return result

    async def get_message_queue_config(self) -> Dict[str, dict]:
        """
        Gets the config dict for the message queue being used.

        Returns:
            Dict[str, dict]: A dict of message queue name -> config dict
        """
        queue_config = self._message_queue.as_config()
        return {queue_config.__class__.__name__: queue_config.model_dump()}

    async def register_to_message_queue(self) -> StartConsumingCallable:
        return await self.message_queue.register_consumer(self.as_consumer(remote=True))


if __name__ == "__main__":
    import asyncio
    from llama_deploy import SimpleMessageQueue, SimpleOrchestrator

    control_plane = ControlPlaneServer(SimpleMessageQueue(), SimpleOrchestrator())

    asyncio.run(control_plane.launch_server())
