import asyncio
import json
import time
from typing import Any, AsyncGenerator, List, Optional

import httpx
from deprecated import deprecated
from llama_index.core.workflow import Event
from llama_index.core.workflow.context_serializers import JsonSerializer

from llama_deploy.control_plane.server import ControlPlaneConfig
from llama_deploy.types import (
    EventDefinition,
    ServiceDefinition,
    SessionDefinition,
    TaskDefinition,
    TaskResult,
)

DEFAULT_TIMEOUT = 120.0
DEFAULT_POLL_INTERVAL = 0.5


@deprecated(reason="This class is deprecated. Please use the 'Client' class instead.")
class AsyncSessionClient:
    def __init__(
        self,
        control_plane_config: ControlPlaneConfig,
        session_id: str,
        timeout: float = DEFAULT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ):
        # TODO: add scheme to config (http, https, ..)
        self.control_plane_url = control_plane_config.url
        self.session_id = session_id
        self.timeout = timeout
        self.poll_interval = poll_interval

    async def run(self, service_name: str, **run_kwargs: Any) -> str:
        """Implements the workflow-based run API for a session."""
        task_input = json.dumps(run_kwargs)
        task_def = TaskDefinition(input=task_input, agent_id=service_name)
        task_id = await self.create_task(task_def)

        # wait for task to complete, up to timeout seconds
        async def _get_result() -> str:
            while True:
                task_result = await self.get_task_result(task_id)
                if isinstance(task_result, TaskResult):
                    return task_result.result or ""
                await asyncio.sleep(self.poll_interval)

        return await asyncio.wait_for(_get_result(), timeout=self.timeout)

    async def run_nowait(self, service_name: str, **run_kwargs: Any) -> str:
        """Implements the workflow-based run API for a session, but does not wait for the task to complete."""

        task_input = json.dumps(run_kwargs)
        task_def = TaskDefinition(input=task_input, agent_id=service_name)
        task_id = await self.create_task(task_def)

        return task_id

    async def create_task(self, task_def: TaskDefinition) -> str:
        """Create a new task in this session.

        Args:
            task_def (Union[str, TaskDefinition]): The task definition or input string.

        Returns:
            str: The ID of the created task.
        """
        task_def.session_id = self.session_id

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.control_plane_url}/sessions/{self.session_id}/tasks",
                json=task_def.model_dump(),
            )
            return response.json()

    async def get_tasks(self) -> List[TaskDefinition]:
        """Get all tasks in this session.

        Returns:
            List[TaskDefinition]: A list of task definitions in the session.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.control_plane_url}/sessions/{self.session_id}/tasks"
            )
            return [TaskDefinition(**task) for task in response.json()]

    async def get_current_task(self) -> Optional[TaskDefinition]:
        """Get the current (most recent) task in this session.

        Returns:
            Optional[TaskDefinition]: The current task definition, or None if the session has no tasks.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.control_plane_url}/sessions/{self.session_id}/current_task"
            )
            data = response.json()
            return TaskDefinition(**data) if data else None

    async def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get the result of a task in this session if it has one.

        Args:
            task_id (str): The ID of the task to get the result for.

        Returns:
            Optional[TaskResult]: The result of the task if it has one, otherwise None.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.control_plane_url}/sessions/{self.session_id}/tasks/{task_id}/result"
            )
            data = response.json()
            return TaskResult(**data) if data else None

    async def get_task_result_stream(
        self, task_id: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Get the result of a task in this session if it has one.

        Args:
            task_id (str): The ID of the task to get the result for.

        Returns:
            AsyncGenerator[str, None, None]: A generator that yields the result of the task.
        """
        start_time = time.time()
        while True:
            try:
                async with httpx.AsyncClient() as client:
                    async with client.stream(
                        "GET",
                        f"{self.control_plane_url}/sessions/{self.session_id}/tasks/{task_id}/result_stream",
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            json_line = json.loads(line)
                            yield json_line
                        break  # Exit the function if successful
            except httpx.HTTPStatusError as e:
                if e.response.status_code != 404:
                    raise  # Re-raise if it's not a 404 error
                if time.time() - start_time < self.timeout:
                    await asyncio.sleep(self.poll_interval)
                else:
                    raise TimeoutError(
                        f"Task result not available after waiting for {self.timeout} seconds"
                    )

    async def send_event(self, service_name: str, task_id: str, ev: Event) -> None:
        """Send event to a Workflow service.

        Args:
            event (Event): The event to be submitted to the workflow.

        Returns:
            None
        """
        serializer = JsonSerializer()
        event_def = EventDefinition(
            event_obj_str=serializer.serialize(ev), agent_id=service_name
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await client.post(
                f"{self.control_plane_url}/sessions/{self.session_id}/tasks/{task_id}/send_event",
                json=event_def.model_dump(),
            )


class AsyncLlamaDeployClient:
    def __init__(
        self, control_plane_config: ControlPlaneConfig, timeout: float = DEFAULT_TIMEOUT
    ):
        self.control_plane_config = control_plane_config
        # TODO: add scheme to config (http, https, ..)
        self.control_plane_url = control_plane_config.url
        self.timeout = timeout

    async def create_session(
        self, poll_interval: float = DEFAULT_POLL_INTERVAL
    ) -> AsyncSessionClient:
        """Create a new session and return a AsyncSessionClient for it.

        Returns:
            AsyncSessionClient: A client for the newly created session.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.control_plane_url}/sessions/create")
            session_id = response.json()
        return AsyncSessionClient(
            self.control_plane_config,
            session_id,
            timeout=self.timeout,
            poll_interval=poll_interval,
        )

    async def list_sessions(self) -> List[SessionDefinition]:
        """List all sessions registered with the control plane.

        Returns:
            List[SessionDefinition]: A list of session definitions.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.control_plane_url}/sessions")
            return [
                SessionDefinition(**session) for session in response.json().values()
            ]

    async def get_session_definition(self, session_id: str) -> SessionDefinition:
        """Get the definition of a session by ID.

        Args:
            session_id (str): The ID of the session to get.

        Returns:
            SessionDefinition: The definition of the session.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.control_plane_url}/sessions/{session_id}"
            )
            return SessionDefinition(**response.json())

    async def get_session(
        self, session_id: str, poll_interval: float = DEFAULT_POLL_INTERVAL
    ) -> AsyncSessionClient:
        """Get an existing session by ID.

        Args:
            session_id (str): The ID of the session to get.

        Returns:
            AsyncSessionClient: A client for the specified session.

        Raises:
            ValueError: If the session does not exist.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.control_plane_url}/sessions/{session_id}"
            )
            if response.status_code == 404:
                raise ValueError(f"Session with id {session_id} not found")
            response.raise_for_status()

        return AsyncSessionClient(
            self.control_plane_config,
            session_id,
            timeout=self.timeout,
            poll_interval=poll_interval,
        )

    async def get_or_create_session(
        self, session_id: str, poll_interval: float = DEFAULT_POLL_INTERVAL
    ) -> AsyncSessionClient:
        """Get an existing session by ID, or create a new one if it doesn't exist.

        Args:
            session_id (str): The ID of the session to get.

        Returns:
            AsyncSessionClient: A client for the specified session.
        """
        try:
            return await self.get_session(session_id, poll_interval=poll_interval)
        except ValueError as e:
            if "not found" in str(e):
                return await self.create_session(poll_interval=poll_interval)
            raise e

    async def get_service(self, service_name: str) -> ServiceDefinition:
        """Get the definition of a service by name.

        Args:
            service_name (str): The name of the service to get.

        Returns:
            ServiceDefinition: The definition of the service.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.control_plane_url}/services/{service_name}"
            )
            return ServiceDefinition(**response.json())

    async def delete_session(self, session_id: str) -> None:
        """Delete a session by ID.

        Args:
            session_id (str): The ID of the session to delete.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await client.post(f"{self.control_plane_url}/sessions/{session_id}/delete")

    async def list_services(self) -> List[ServiceDefinition]:
        """List all services registered with the control plane.

        Returns:
            List[ServiceDefinition]: A list of service definitions.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.control_plane_url}/services")
            return [
                ServiceDefinition(**service) for _, service in response.json().items()
            ]

    async def register_service(self, service_def: ServiceDefinition) -> None:
        """Register a service with the control plane.

        Args:
            service_def (ServiceDefinition): The service definition to register.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await client.post(
                f"{self.control_plane_url}/services/register",
                json=service_def.model_dump(),
            )

    async def deregister_service(self, service_name: str) -> None:
        """Deregister a service from the control plane.

        Args:
            service_name (str): The name of the service to deregister.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            await client.post(
                f"{self.control_plane_url}/services/deregister",
                json={"service_name": service_name},
            )
