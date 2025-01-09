import asyncio
import json
import uuid
from logging import getLogger
from typing import Any, AsyncGenerator, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from llama_index.core.storage.kvstore import SimpleKVStore
from llama_index.core.storage.kvstore.types import BaseKVStore

from llama_deploy.control_plane.base import BaseControlPlane
from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)
from llama_deploy.message_consumers.callable import CallableMessageConsumer
from llama_deploy.message_consumers.remote import RemoteMessageConsumer
from llama_deploy.message_queues.base import AbstractMessageQueue, PublishCallback
from llama_deploy.messages.base import QueueMessage
from llama_deploy.orchestrators import SimpleOrchestrator, SimpleOrchestratorConfig
from llama_deploy.orchestrators.base import BaseOrchestrator
from llama_deploy.orchestrators.utils import get_result_key, get_stream_key
from llama_deploy.types import (
    ActionTypes,
    EventDefinition,
    ServiceDefinition,
    SessionDefinition,
    TaskDefinition,
    TaskResult,
    TaskStream,
)

from .config import ControlPlaneConfig, parse_state_store_uri

logger = getLogger(__name__)

CONTROL_PLANE_MESSAGE_TYPE = "control_plane"


class ControlPlaneServer(BaseControlPlane):
    """Control plane server.

    The control plane is responsible for managing the state of the system, including:
    - Registering services.
    - Submitting tasks.
    - Managing task state.
    - Handling service completion.
    - Launching the control plane server.

    Args:
        message_queue (AbstractMessageQueue): Message queue for the system.
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
        cors_origins (Optional[List[str]], optional): List of hosts from which the service will accept CORS requests.  Use '["*"]' for all hosts.

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
        message_queue: AbstractMessageQueue,
        orchestrator: BaseOrchestrator | None = None,
        publish_callback: PublishCallback | None = None,
        state_store: BaseKVStore | None = None,
        config: ControlPlaneConfig | None = None,
    ) -> None:
        self._orchestrator = orchestrator or SimpleOrchestrator(
            **SimpleOrchestratorConfig().model_dump()
        )
        self._config = config or ControlPlaneConfig()

        if state_store is not None and self._config.state_store_uri is not None:
            raise ValueError("Please use either 'state_store' or 'state_store_uri'.")

        if state_store:
            self._state_store = state_store
        elif self._config.state_store_uri:
            self._state_store = parse_state_store_uri(self._config.state_store_uri)
        else:
            self._state_store = state_store or SimpleKVStore()

        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback

        self.app = FastAPI()
        if self._config.cors_origins:
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=self._config.cors_origins,
                allow_methods=["*"],
                allow_headers=["*"],
            )
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
        self.app.add_api_route(
            "/sessions/{session_id}/tasks/{task_id}/result_stream",
            self.get_task_result_stream,
            methods=["GET"],
            tags=["Sessions"],
        )
        self.app.add_api_route(
            "/sessions/{session_id}/tasks/{task_id}/send_event",
            self.send_event,
            methods=["POST"],
            tags=["Sessions"],
        )
        self.app.add_api_route(
            "/sessions/{session_id}/state",
            self.get_session_state,
            methods=["GET"],
            tags=["Sessions"],
        )
        self.app.add_api_route(
            "/sessions/{session_id}/state",
            self.update_session_state,
            methods=["POST"],
            tags=["Sessions"],
        )

    @property
    def message_queue(self) -> AbstractMessageQueue:
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
        elif action == ActionTypes.TASK_STREAM and message.data is not None:
            await self.add_stream_to_session(TaskStream(**message.data))
        else:
            raise ValueError(f"Action {action} not supported by control plane")

    def as_consumer(self, remote: bool = False) -> BaseMessageQueueConsumer:
        if remote:
            return RemoteMessageConsumer(
                id_=self.publisher_id,
                url=(
                    f"http://{self._config.host}:{self._config.port}/process_message"
                    if self._config.port
                    else f"http://{self._config.host}/process_message"
                ),
                message_type=CONTROL_PLANE_MESSAGE_TYPE,
            )

        return CallableMessageConsumer(
            id_=self.publisher_id,
            message_type=CONTROL_PLANE_MESSAGE_TYPE,
            handler=self.process_message,
        )

    async def launch_server(self) -> None:
        # give precedence to external settings
        host = self._config.internal_host or self._config.host
        port = self._config.internal_port or self._config.port
        logger.info(f"Launching control plane server at {host}:{port}")
        # uvicorn.run(self.app, host=self._config.host, port=self._config.port)

        class CustomServer(uvicorn.Server):
            def install_signal_handlers(self) -> None:
                pass

        cfg = uvicorn.Config(self.app, host=host, port=port)
        server = CustomServer(cfg)
        try:
            await server.serve()
        except asyncio.CancelledError:
            self._running = False
            await asyncio.gather(server.shutdown(), return_exceptions=True)

    async def home(self) -> Dict[str, str]:
        return {
            "running": str(self._config.running),
            "step_interval": str(self._config.step_interval),
            "services_store_key": self._config.services_store_key,
            "tasks_store_key": self._config.tasks_store_key,
            "session_store_key": self._config.session_store_key,
        }

    async def register_service(
        self, service_def: ServiceDefinition
    ) -> ControlPlaneConfig:
        await self._state_store.aput(
            service_def.service_name,
            service_def.model_dump(),
            collection=self._config.services_store_key,
        )
        return self._config

    async def deregister_service(self, service_name: str) -> None:
        await self._state_store.adelete(
            service_name, collection=self._config.services_store_key
        )

    async def get_service(self, service_name: str) -> ServiceDefinition:
        service_dict = await self._state_store.aget(
            service_name, collection=self._config.services_store_key
        )
        if service_dict is None:
            raise HTTPException(status_code=404, detail="Service not found")

        return ServiceDefinition.model_validate(service_dict)

    async def get_all_services(self) -> Dict[str, ServiceDefinition]:
        service_dicts = await self._state_store.aget_all(
            collection=self._config.services_store_key
        )

        return {
            service_name: ServiceDefinition.model_validate(service_dict)
            for service_name, service_dict in service_dicts.items()
        }

    async def create_session(self) -> str:
        session = SessionDefinition()
        await self._state_store.aput(
            session.session_id,
            session.model_dump(),
            collection=self._config.session_store_key,
        )

        return session.session_id

    async def get_session(self, session_id: str) -> SessionDefinition:
        session_dict = await self._state_store.aget(
            session_id, collection=self._config.session_store_key
        )
        if session_dict is None:
            raise HTTPException(status_code=404, detail="Session not found")

        return SessionDefinition.model_validate(session_dict)

    async def delete_session(self, session_id: str) -> None:
        await self._state_store.adelete(
            session_id, collection=self._config.session_store_key
        )

    async def get_all_sessions(self) -> Dict[str, SessionDefinition]:
        session_dicts = await self._state_store.aget_all(
            collection=self._config.session_store_key
        )

        return {
            session_id: SessionDefinition.model_validate(session_dict)
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
        session_dict = await self._state_store.aget(
            session_id, collection=self._config.session_store_key
        )
        if session_dict is None:
            raise HTTPException(status_code=404, detail="Session not found")

        if not task_def.session_id:
            task_def.session_id = session_id

        session = SessionDefinition(**session_dict)
        session.task_ids.append(task_def.task_id)
        await self._state_store.aput(
            session_id, session.model_dump(), collection=self._config.session_store_key
        )

        await self._state_store.aput(
            task_def.task_id,
            task_def.model_dump(),
            collection=self._config.tasks_store_key,
        )

        task_def = await self.send_task_to_service(task_def)

        return task_def.task_id

    async def send_task_to_service(self, task_def: TaskDefinition) -> TaskDefinition:
        if task_def.session_id is None:
            raise ValueError(f"Task with id {task_def.task_id} has no session")

        session = await self.get_session(task_def.session_id)

        next_messages, session_state = await self._orchestrator.get_next_messages(
            task_def, session.state
        )

        logger.debug(f"Sending task {task_def.task_id} to services: {next_messages}")

        for message in next_messages:
            await self.publish(message)

        session.state.update(session_state)

        await self._state_store.aput(
            task_def.session_id,
            session.model_dump(),
            collection=self._config.session_store_key,
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
        state = await self._orchestrator.add_result_to_state(task_result, session.state)

        # update session state
        session.state.update(state)
        await self._state_store.aput(
            session.session_id,
            session.model_dump(),
            collection=self._config.session_store_key,
        )

        # generate and send new tasks when needed
        task_def = await self.send_task_to_service(task_def)

        await self._state_store.aput(
            task_def.task_id,
            task_def.model_dump(),
            collection=self._config.tasks_store_key,
        )

    async def get_task(self, task_id: str) -> TaskDefinition:
        state_dict = await self._state_store.aget(
            task_id, collection=self._config.tasks_store_key
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

    async def add_stream_to_session(self, task_stream: TaskStream) -> None:
        # get session
        if task_stream.session_id is None:
            raise ValueError(
                f"Task stream with id {task_stream.task_id} has no session"
            )

        session = await self.get_session(task_stream.session_id)

        # add new stream data to session state
        existing_stream = session.state.get(get_stream_key(task_stream.task_id), [])
        existing_stream.append(task_stream.model_dump())
        session.state[get_stream_key(task_stream.task_id)] = existing_stream

        # update session state in store
        await self._state_store.aput(
            task_stream.session_id,
            session.model_dump(),
            collection=self._config.session_store_key,
        )

    async def get_task_result_stream(
        self, session_id: str, task_id: str
    ) -> StreamingResponse:
        session = await self.get_session(session_id)

        stream_key = get_stream_key(task_id)
        if stream_key not in session.state:
            raise HTTPException(status_code=404, detail="Task stream not found")

        async def event_generator(
            session: SessionDefinition, stream_key: str
        ) -> AsyncGenerator[str, None]:
            try:
                last_index = 0
                while True:
                    session = await self.get_session(session_id)
                    stream_results = session.state[stream_key][last_index:]
                    stream_results = sorted(stream_results, key=lambda x: x["index"])
                    for result in stream_results:
                        if not isinstance(result, TaskStream):
                            if isinstance(result, dict):
                                result = TaskStream(**result)
                            elif isinstance(result, str):
                                result = TaskStream(**json.loads(result))
                            else:
                                raise ValueError("Unexpected result type in stream")

                        yield json.dumps(result.data) + "\n"

                    # check if there is a final result
                    final_result = await self.get_task_result(task_id, session_id)
                    if final_result is not None:
                        return

                    last_index += len(stream_results)
                    # Small delay to prevent tight loop
                    await asyncio.sleep(self._config.step_interval)
            except Exception as e:
                logger.error(
                    f"Error in event stream for session {session_id}, task {task_id}: {str(e)}"
                )
                yield json.dumps({"error": str(e)}) + "\n"

        return StreamingResponse(
            event_generator(session, stream_key),
            media_type="application/x-ndjson",
        )

    async def send_event(
        self,
        session_id: str,
        task_id: str,
        event_def: EventDefinition,
    ) -> None:
        task_def = TaskDefinition(
            task_id=task_id,
            session_id=session_id,
            input=event_def.event_obj_str,
            agent_id=event_def.agent_id,
        )
        message = QueueMessage(
            type=event_def.agent_id,
            action=ActionTypes.SEND_EVENT,
            data=task_def.model_dump(),
        )
        await self.publish(message)

    async def get_session_state(self, session_id: str) -> Dict[str, Any]:
        session = await self.get_session(session_id)
        if session.task_ids is None:
            raise HTTPException(status_code=404, detail="Session not found")

        return session.state

    async def update_session_state(
        self, session_id: str, state: Dict[str, Any]
    ) -> None:
        session = await self.get_session(session_id)

        session.state.update(state)
        await self._state_store.aput(
            session_id, session.model_dump(), collection=self._config.session_store_key
        )

    async def get_message_queue_config(self) -> Dict[str, dict]:
        """
        Gets the config dict for the message queue being used.

        Returns:
            Dict[str, dict]: A dict of message queue name -> config dict
        """
        queue_config = self._message_queue.as_config()
        return {queue_config.__class__.__name__: queue_config.model_dump()}

    async def register_to_message_queue(self) -> StartConsumingCallable:
        return await self.message_queue.register_consumer(
            self.as_consumer(remote=True),
            topic=self.get_topic(CONTROL_PLANE_MESSAGE_TYPE),
        )

    def get_topic(self, msg_type: str) -> str:
        return f"{self._config.topic_namespace}.{msg_type}"
