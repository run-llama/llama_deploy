"""
What does the processing loop for the control plane look like?
- check message queue
- handle incoming new tasks
- handle incoming general chats
- handle services returning a completed task
"""

from abc import ABC, abstractmethod
from typing import Dict

from llama_agents.message_queues.base import BaseMessageQueue
from llama_agents.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)
from llama_agents.message_publishers.publisher import MessageQueuePublisherMixin
from llama_agents.types import (
    ServiceDefinition,
    TaskDefinition,
    TaskResult,
)


class BaseControlPlane(MessageQueuePublisherMixin, ABC):
    """The control plane for the system.

    The control plane is responsible for managing the state of the system, including:
    - Registering services.
    - Submitting tasks.
    - Managing task state.
    - Handling service completion.
    - Launching the control plane server.
    """

    @property
    @abstractmethod
    def message_queue(self) -> BaseMessageQueue:
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
        ...

    @abstractmethod
    async def register_service(self, service_def: ServiceDefinition) -> None:
        """
        Register an service with the control plane.

        Args:
            service_def (ServiceDefinition): Definition of the service.
        """
        ...

    @abstractmethod
    async def deregister_service(self, service_name: str) -> None:
        """
        Deregister a service from the control plane.

        Args:
            service_name (str): Name of the service.
        """
        ...

    @abstractmethod
    async def create_task(self, task_def: TaskDefinition) -> Dict[str, str]:
        """
        Submit a task to the control plane.

        Args:
            task_def (TaskDefinition): Definition of the task.

        Returns:
            dict: Task ID.
        """
        ...

    @abstractmethod
    async def send_task_to_service(self, task_def: TaskDefinition) -> TaskDefinition:
        """
        Send a task to an service.

        Args:
            task_def (TaskDefinition): Definition of the task.

        Returns:
            TaskDefinition: Task definition with updated state.
        """
        ...

    @abstractmethod
    async def handle_service_completion(
        self,
        task_result: TaskResult,
    ) -> None:
        """
        Handle the completion of a task by an service.

        Args:
            task_result (TaskResult): Result of the task.
        """
        ...

    @abstractmethod
    async def get_task_state(self, task_id: str) -> dict:
        """
        Get the current state of a task.

        Args:
            task_id (str): Unique identifier of the task.

        Returns:
            dict: State of the task
        """
        ...

    @abstractmethod
    async def get_all_tasks(self) -> dict:
        """
        Get all tasks.

        Returns:
            dict: All tasks.
        """
        ...

    @abstractmethod
    async def launch_server(self) -> None:
        """
        Launch the control plane server.
        """
        ...

    @abstractmethod
    async def register_to_message_queue(self) -> StartConsumingCallable:
        """Register the service to the message queue."""
