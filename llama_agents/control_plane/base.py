"""
What does the processing loop for the control plane look like?
- check message queue
- handle incoming new tasks
- handle incoming general chats
- handle services returning a completed task
"""

from abc import ABC, abstractmethod
from typing import Dict

from llama_agents.message_consumers.base import BaseMessageQueueConsumer
from llama_agents.message_publishers.publisher import MessageQueuePublisherMixin
from llama_agents.types import (
    ServiceDefinition,
    TaskDefinition,
    TaskResult,
)


class BaseControlPlane(MessageQueuePublisherMixin, ABC):
    @abstractmethod
    def as_consumer(self, remote: bool = False) -> BaseMessageQueueConsumer:
        """
        Get the consumer for the message queue.

        :return: Consumer for the message queue.
        """
        ...

    @abstractmethod
    async def register_service(self, service_def: ServiceDefinition) -> None:
        """
        Register an service with the control plane.

        :param service_def: Definition of the service.
        """
        ...

    @abstractmethod
    async def deregister_service(self, service_name: str) -> None:
        """
        Deregister a service from the control plane.

        :param service_name: Unique identifier of the service.
        """
        ...

    @abstractmethod
    async def create_task(self, task_def: TaskDefinition) -> Dict[str, str]:
        """
        Submit a task to the control plane.

        :param task_def: Definition of the task.
        """
        ...

    @abstractmethod
    async def send_task_to_service(self, task_def: TaskDefinition) -> TaskDefinition:
        """
        Send a task to an service.

        :param task_def: Definition of the task.
        """
        ...

    @abstractmethod
    async def handle_service_completion(
        self,
        task_result: TaskResult,
    ) -> None:
        """
        Handle the completion of a task by an service.

        :param task_result: Result of the task.
        """
        ...

    @abstractmethod
    async def get_task_state(self, task_id: str) -> dict:
        """
        Get the current state of a task.

        :param task_id: Unique identifier of the task.
        :return: Current state of the task.
        """
        ...

    @abstractmethod
    async def get_all_tasks(self) -> dict:
        """
        Get all tasks.

        :return: All tasks.
        """
        ...

    @abstractmethod
    async def launch_server(self) -> None:
        """
        Launch the control plane server.
        """
        ...
