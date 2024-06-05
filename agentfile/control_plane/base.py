"""
What does the processing loop for the control plane look like?
- check message queue
- handle incoming new tasks
- handle incoming general chats
- handle agents returning a completed task
"""

from abc import ABC, abstractmethod


class BaseControlPlane(ABC):
    @abstractmethod
    def register_agent(self, agent_id: str, agent_role: str) -> None:
        """
        Register an agent with the control plane.

        :param agent_id: Unique identifier of the agent.
        :param agent_role: Role of the agent.
        """
        ...

    @abstractmethod
    def deregister_agent(self, agent_id: str) -> None:
        """
        Deregister an agent from the control plane.

        :param agent_id: Unique identifier of the agent.
        """
        ...

    @abstractmethod
    def register_flow(self, flow_id: str, flow_definition: dict) -> None:
        """
        Register a flow with the control plane.

        :param flow_id: Unique identifier of the flow.
        :param flow_definition: Definition of the flow.
        """
        ...

    @abstractmethod
    def deregister_flow(self, flow_id: str) -> None:
        """
        Deregister a flow from the control plane.

        :param flow_id: Unique identifier of the flow.
        """
        ...

    @abstractmethod
    def handle_new_task(self, task_id: str, task_definition: dict) -> None:
        """
        Submit a task to the control plane.

        :param task_id: Unique identifier of the task.
        :param task_definition: Definition of the task.
        """
        ...

    @abstractmethod
    def send_task_to_agent(self, task_id: str, agent_id: str) -> None:
        """
        Send a task to an agent.

        :param task_id: Unique identifier of the task.
        :param agent_id: Unique identifier of the agent.
        """
        ...

    @abstractmethod
    def handle_agent_completion(
        self, task_id: str, agent_id: str, result: dict
    ) -> None:
        """
        Handle the completion of a task by an agent.

        :param task_id: Unique identifier of the task.
        :param agent_id: Unique identifier of the agent.
        :param result: Result of the task.
        """
        ...

    @abstractmethod
    def get_next_agent(self, task_id: str) -> str:
        """
        Get the next agent for a task.

        :param task_id: Unique identifier of the task.
        :return: Unique identifier of the next agent.
        """
        ...

    @abstractmethod
    def get_task_state(self, task_id: str) -> dict:
        """
        Get the current state of a task.

        :param task_id: Unique identifier of the task.
        :return: Current state of the task.
        """
        ...

    @abstractmethod
    def request_user_input(self, task_id: str, message: str) -> None:
        """
        Request input from the user for a task.

        :param task_id: Unique identifier of the task.
        :param message: Message to send to the user.
        """
        ...

    @abstractmethod
    def handle_user_input(self, task_id: str, user_input: str) -> None:
        """
        Handle the user input for a task.

        :param task_id: Unique identifier of the task.
        :param user_input: Input provided by the user.
        """
        ...
