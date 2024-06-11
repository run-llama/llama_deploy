"""
What does the processing loop for the control plane look like?
- check message queue
- handle incoming new tasks
- handle incoming general chats
- handle services returning a completed task
"""

from abc import ABC, abstractmethod

from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.types import (
    ServiceDefinition,
    FlowDefinition,
    TaskDefinition,
    TaskResult,
)


class BaseControlPlane(ABC):
    @abstractmethod
    def as_consumer(self) -> BaseMessageQueueConsumer:
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
    async def register_flow(self, flow_def: FlowDefinition) -> None:
        """
        Register a flow with the control plane.

        :param flow_def: Definition of the flow.
        """
        ...

    @abstractmethod
    async def deregister_flow(self, flow_id: str) -> None:
        """
        Deregister a flow from the control plane.

        :param flow_id: Unique identifier of the flow.
        """
        ...

    @abstractmethod
    async def create_task(self, task_def: TaskDefinition) -> None:
        """
        Submit a task to the control plane.

        :param task_def: Definition of the task.
        """
        ...

    @abstractmethod
    async def send_task_to_service(self, task_def: TaskDefinition) -> None:
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
    async def get_next_service(self, task_id: str) -> str:
        """
        Get the next service for a task.

        :param task_id: Unique identifier of the task.
        :return: Unique identifier of the next service.
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
    async def request_user_input(self, task_id: str, message: str) -> None:
        """
        Request input from the user for a task.

        :param task_id: Unique identifier of the task.
        :param message: Message to send to the user.
        """
        ...

    @abstractmethod
    async def handle_user_input(self, task_id: str, user_input: str) -> None:
        """
        Handle the user input for a task.

        :param task_id: Unique identifier of the task.
        :param user_input: Input provided by the user.
        """
        ...
