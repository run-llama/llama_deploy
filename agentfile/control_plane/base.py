"""
What does the processing loop for the control plane look like?
- check message queue
- handle incoming new tasks
- handle incoming general chats
- handle agents returning a completed task
"""

from abc import ABC, abstractmethod

from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.types import AgentDefinition, FlowDefinition, TaskDefinition, TaskResult
from agentfile.message_publishers.publisher import MessageQueuePublisherMixin


class BaseControlPlane(MessageQueuePublisherMixin, ABC):
    @abstractmethod
    def get_consumer(self) -> BaseMessageQueueConsumer:
        """
        Get the consumer for the message queue.

        :return: Consumer for the message queue.
        """
        ...

    @abstractmethod
    async def register_agent(self, agent_def: AgentDefinition) -> None:
        """
        Register an agent with the control plane.

        :param agent_def: Definition of the agent.
        """
        ...

    @abstractmethod
    async def deregister_agent(self, agent_id: str) -> None:
        """
        Deregister an agent from the control plane.

        :param agent_id: Unique identifier of the agent.
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
    async def send_task_to_agent(self, task_def: TaskDefinition) -> None:
        """
        Send a task to an agent.

        :param task_def: Definition of the task.
        """
        ...

    @abstractmethod
    async def handle_agent_completion(
        self,
        task_result: TaskResult,
    ) -> None:
        """
        Handle the completion of a task by an agent.

        :param task_result: Result of the task.
        """
        ...

    @abstractmethod
    async def get_next_agent(self, task_id: str) -> str:
        """
        Get the next agent for a task.

        :param task_id: Unique identifier of the task.
        :return: Unique identifier of the next agent.
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
