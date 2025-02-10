from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)
from llama_deploy.message_publishers.publisher import MessageQueuePublisherMixin
from llama_deploy.message_queues.base import AbstractMessageQueue
from llama_deploy.types import (
    ServiceDefinition,
    SessionDefinition,
    TaskDefinition,
    TaskResult,
)

from .config import ControlPlaneConfig


class BaseControlPlane(MessageQueuePublisherMixin, ABC):
    """The control plane for the system.

    The control plane is responsible for managing the state of the system, including:
    - Registering services.
    - Managing sessions and tasks.
    - Handling service completion.
    - Launching the control plane server.
    """

    @property
    @abstractmethod
    def message_queue(self) -> AbstractMessageQueue:
        """Return associated message queue."""

    @abstractmethod
    def as_consumer(self, remote: bool = False) -> BaseMessageQueueConsumer:
        """
        Get the consumer for the message queue.

        Args:
            remote (bool):
                Whether the consumer is remote.
                If True, the consumer will be a RemoteMessageConsumer.

        Returns:
            BaseMessageQueueConsumer: Message queue consumer.
        """

    @abstractmethod
    async def register_service(
        self, service_def: ServiceDefinition
    ) -> ControlPlaneConfig:
        """
        Register a service with the control plane.

        Args:
            service_def (ServiceDefinition): Definition of the service.
        """

    @abstractmethod
    async def deregister_service(self, service_name: str) -> None:
        """
        Deregister a service from the control plane.

        Args:
            service_name (str): Name of the service.
        """

    @abstractmethod
    async def get_service(self, service_name: str) -> ServiceDefinition:
        """
        Get the definition of a service by name.

        Args:
            service_name (str): Name of the service.

        Returns:
            ServiceDefinition: Definition of the service.
        """

    @abstractmethod
    async def get_all_services(self) -> Dict[str, ServiceDefinition]:
        """
        Get all services registered with the control plane.

        Returns:
            dict: All services, mapped from service name to service definition.
        """

    @abstractmethod
    async def create_session(self) -> str:
        """
        Create a new session.

        Returns:
            str: Session ID.
        """

    @abstractmethod
    async def add_task_to_session(
        self, session_id: str, task_def: TaskDefinition
    ) -> str:
        """
        Add a task to an existing session.

        Args:
            session_id (str): ID of the session.
            task_def (TaskDefinition): Definition of the task.

        Returns:
            str: Task ID.
        """

    @abstractmethod
    async def send_task_to_service(self, task_def: TaskDefinition) -> TaskDefinition:
        """
        Send a task to a service.

        Args:
            task_def (TaskDefinition): Definition of the task.

        Returns:
            TaskDefinition: Task definition with updated state.
        """

    @abstractmethod
    async def handle_service_completion(
        self,
        task_result: TaskResult,
    ) -> None:
        """
        Handle the completion of a task by a service.

        Args:
            task_result (TaskResult): Result of the task.
        """

    @abstractmethod
    async def get_session(self, session_id: str) -> SessionDefinition:
        """
        Get the specified session session.

        Args:
            session_id (str): Unique identifier of the session.

        Returns:
            SessionDefinition: The session definition.
        """

    @abstractmethod
    async def delete_session(self, session_id: str) -> None:
        """
        Delete the specified session.

        Args:
            session_id (str): Unique identifier of the session.
        """

    @abstractmethod
    async def get_all_sessions(self) -> Dict[str, SessionDefinition]:
        """
        Get all sessions.

        Returns:
            dict: All sessions, mapped from session ID to session definition.
        """

    @abstractmethod
    async def get_session_tasks(self, session_id: str) -> List[TaskDefinition]:
        """
        Get all tasks for a session.

        Args:
            session_id (str): Unique identifier of the session.

        Returns:
            List[TaskDefinition]: All tasks in the session.
        """

    @abstractmethod
    async def get_current_task(self, session_id: str) -> Optional[TaskDefinition]:
        """
        Get the current task for a session.

        Args:
            session_id (str): Unique identifier of the session.

        Returns:
            Optional[TaskDefinition]: The current task, if any.
        """

    @abstractmethod
    async def get_task(self, task_id: str) -> TaskDefinition:
        """
        Get the specified task.

        Args:
            task_id (str): Unique identifier of the task.

        Returns:
            TaskDefinition: The task definition.
        """

    @abstractmethod
    async def get_message_queue_config(self) -> Dict[str, dict]:
        """
        Gets the config dict for the message queue being used.

        Returns:
            Dict[str, dict]: A dict of message queue name -> config dict
        """

    @abstractmethod
    async def launch_server(self) -> None:
        """
        Launch the control plane server.
        """

    @abstractmethod
    async def register_to_message_queue(self) -> StartConsumingCallable:
        """Register the service to the message queue."""
