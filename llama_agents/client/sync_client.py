import httpx
from typing import Dict, Optional, Union

from llama_agents.types import TaskDefinition, ServiceDefinition, TaskResult

DEFAULT_TIMEOUT = 120.0


class LlamaAgentsClient:
    """Client for interacting with the Llama Agents control plane synchronously.

    Args:
        control_plane_url (str): The URL of the control plane.
        timeout (float, optional): The timeout for requests. Defaults to 120.0.
    """

    def __init__(self, control_plane_url: str, timeout: float = DEFAULT_TIMEOUT):
        self.control_plane_url = control_plane_url
        self.timeout = timeout

    def create_task(self, task_def: Union[str, TaskDefinition]) -> str:
        """Create a new task with the control plane.

        Args:
            task_def (Union[str, TaskDefinition]):
                The task definition to create.
                If a string is provided, it will be used as the input for the task.

        Returns:
            str: The ID of the created task.
        """
        if isinstance(task_def, str):
            task_def = TaskDefinition(input=task_def)

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.control_plane_url}/tasks", json=task_def.model_dump()
            )
            return response.json()["task_id"]

    def get_tasks(self) -> Dict[str, TaskDefinition]:
        """Get all tasks registered with the control plane.

        Returns:
            Dict[str, TaskDefinition]: A dictionary of task IDs to task definitions
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.control_plane_url}/tasks")
            task_dicts = response.json()

        return {
            task_id: TaskDefinition(**task_dict)
            for task_id, task_dict in task_dicts.items()
        }

    def get_task(self, task_id: str) -> TaskDefinition:
        """Get a task by ID.

        Args:
            task_id (str): The ID of the task to get.

        Returns:
            TaskDefinition: The definition of the task.
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.control_plane_url}/tasks/{task_id}")
            return TaskDefinition(**response.json())

    def get_services(self) -> Dict[str, ServiceDefinition]:
        """Get all services registered with the control plane.

        Returns:
            Dict[str, ServiceDefinition]: A dictionary of service names to service definitions
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.control_plane_url}/services")
            service_def_dicts = response.json()

        return {
            service_name: ServiceDefinition(**service_def_dict)
            for service_name, service_def_dict in service_def_dicts.items()
        }

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

    def register_service(self, service_def: ServiceDefinition) -> None:
        """Register a service with the control plane.

        Args:
            service_def (ServiceDefinition): The service definition to register.

        Returns:
            None
        """
        with httpx.Client(timeout=self.timeout) as client:
            client.post(
                f"{self.control_plane_url}/services", json=service_def.model_dump()
            )

    def deregister_service(self, service_name: str) -> None:
        """Deregister a service from the control plane.

        Args:
            service_name (str): The name of the service to deregister.

        Returns:
            None
        """
        with httpx.Client(timeout=self.timeout) as client:
            client.delete(f"{self.control_plane_url}/services/{service_name}")

    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get the result of a task if it has one.

        Args:
            task_id (str): The ID of the task to get the result for.

        Returns:
            Optional[TaskResult]: The result of the task if it has one.
        """
        task = self.get_task(task_id)

        try:
            return TaskResult(**task.state["result"])
        except KeyError:
            raise ValueError(f"Task {task_id} does not have a result yet.")
