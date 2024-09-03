import httpx
import json
import time
from typing import Any, List, Optional

from llama_deploy.control_plane.server import ControlPlaneConfig
from llama_deploy.types import (
    TaskDefinition,
    ServiceDefinition,
    TaskResult,
    SessionDefinition,
)

DEFAULT_TIMEOUT = 120.0
DEFAULT_POLL_INTERVAL = 0.1


class SessionClient:
    def __init__(
        self,
        control_plane_config: ControlPlaneConfig,
        session_id: str,
        timeout: float = DEFAULT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ):
        # TODO: add scheme to config (http, https, ..)
        self.control_plane_url = (
            f"http://{control_plane_config.host}:{control_plane_config.port}"
        )
        self.session_id = session_id
        self.timeout = timeout
        self.poll_interval = poll_interval

    def run(self, service_name: str, **run_kwargs: Any) -> str:
        """Implements the workflow-based run API for a session."""
        task_input = json.dumps(run_kwargs)
        task_def = TaskDefinition(input=task_input, agent_id=service_name)
        task_id = self.create_task(task_def)

        # wait for task to complete, up to timeout seconds
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            result = self.get_task_result(task_id)
            if isinstance(result, TaskResult):
                return result.result
            time.sleep(self.poll_interval)

        raise TimeoutError(f"Task {task_id} timed out after {self.timeout} seconds")

    def create_task(self, task_def: TaskDefinition) -> str:
        """Create a new task in this session.

        Args:
            task_def (Union[str, TaskDefinition]): The task definition or input string.

        Returns:
            str: The ID of the created task.
        """
        task_def.session_id = self.session_id

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.control_plane_url}/sessions/{self.session_id}/tasks",
                json=task_def.model_dump(),
            )
            return response.json()

    def get_tasks(self) -> List[TaskDefinition]:
        """Get all tasks in this session.

        Returns:
            List[TaskDefinition]: A list of task definitions in the session.
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.control_plane_url}/sessions/{self.session_id}/tasks"
            )
            return [TaskDefinition(**task) for task in response.json()]

    def get_current_task(self) -> Optional[TaskDefinition]:
        """Get the current (most recent) task in this session.

        Returns:
            Optional[TaskDefinition]: The current task definition, or None if the session has no tasks.
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.control_plane_url}/sessions/{self.session_id}/current_task"
            )
            data = response.json()
            return TaskDefinition(**data) if data else None

    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get the result of a task in this session if it has one.

        Args:
            task_id (str): The ID of the task to get the result for.

        Returns:
            Optional[TaskResult]: The result of the task if it has one, otherwise None.
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.control_plane_url}/sessions/{self.session_id}/tasks/{task_id}/result"
            )
            data = response.json()
            return TaskResult(**data) if data else None


class LlamaDeployClient:
    def __init__(
        self, control_plane_config: ControlPlaneConfig, timeout: float = DEFAULT_TIMEOUT
    ):
        self.control_plane_config = control_plane_config
        # TODO: add scheme to config (http, https, ..)
        self.control_plane_url = (
            f"http://{control_plane_config.host}:{control_plane_config.port}"
        )
        self.timeout = timeout

    def create_session(
        self, poll_interval: float = DEFAULT_POLL_INTERVAL
    ) -> SessionClient:
        """Create a new session and return a SessionClient for it.

        Returns:
            SessionClient: A client for the newly created session.
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.control_plane_url}/sessions/create")
            session_id = response.json()
        return SessionClient(
            self.control_plane_config,
            session_id,
            timeout=self.timeout,
            poll_interval=poll_interval,
        )

    def list_sessions(self) -> List[SessionDefinition]:
        """List all sessions registered with the control plane.

        Returns:
            List[SessionDefinition]: A list of session definitions.
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.control_plane_url}/sessions")
            return [SessionDefinition(**session) for session in response.json()]

    def get_session(
        self, session_id: str, poll_interval: float = DEFAULT_POLL_INTERVAL
    ) -> SessionClient:
        """Get an existing session by ID.

        Args:
            session_id (str): The ID of the session to get.

        Returns:
            SessionClient: A client for the specified session.

        Raises:
            ValueError: If the session does not exist.
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.control_plane_url}/sessions/{session_id}")
            if response.status_code == 404:
                raise ValueError(f"Session with id {session_id} not found")
            response.raise_for_status()

        return SessionClient(
            self.control_plane_config,
            session_id,
            timeout=self.timeout,
            poll_interval=poll_interval,
        )

    def get_or_create_session(
        self, session_id: str, poll_interval: float = DEFAULT_POLL_INTERVAL
    ) -> SessionClient:
        """Get an existing session by ID, or create a new one if it doesn't exist.

        Args:
            session_id (str): The ID of the session to get.

        Returns:
            SessionClient: A client for the specified session.
        """
        try:
            return self.get_session(session_id, poll_interval=poll_interval)
        except ValueError as e:
            if "not found" in str(e):
                return self.create_session(poll_interval=poll_interval)
            raise e

    def get_service(self, service_name: str) -> ServiceDefinition:
        """Get the definition of a service by name.

        Args:
            service_name (str): The name of the service to get.

        Returns:
            ServiceDefinition: The definition of the service.
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.control_plane_url}/services/{service_name}")
            return ServiceDefinition(**response.json())

    def delete_session(self, session_id: str) -> None:
        """Delete a session by ID.

        Args:
            session_id (str): The ID of the session to delete.
        """
        with httpx.Client(timeout=self.timeout) as client:
            client.post(f"{self.control_plane_url}/sessions/{session_id}/delete")

    def list_services(self) -> List[ServiceDefinition]:
        """List all services registered with the control plane.

        Returns:
            List[ServiceDefinition]: A list of service definitions.
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.control_plane_url}/services")
            return [
                ServiceDefinition(**service) for _, service in response.json().items()
            ]

    def register_service(self, service_def: ServiceDefinition) -> None:
        """Register a service with the control plane.

        Args:
            service_def (ServiceDefinition): The service definition to register.
        """
        with httpx.Client(timeout=self.timeout) as client:
            client.post(
                f"{self.control_plane_url}/services/register",
                json=service_def.model_dump(),
            )

    def deregister_service(self, service_name: str) -> None:
        """Deregister a service from the control plane.

        Args:
            service_name (str): The name of the service to deregister.
        """
        with httpx.Client(timeout=self.timeout) as client:
            client.post(
                f"{self.control_plane_url}/services/deregister",
                json={"service_name": service_name},
            )
