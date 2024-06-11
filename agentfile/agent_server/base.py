from abc import ABC, abstractmethod
from typing import Dict, List

from agentfile.agent_server.types import _Task, _TaskSate, _TaskStep, _TaskStepOutput
from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.message_publishers.publisher import MessageQueuePublisherMixin
from agentfile.types import AgentDefinition, TaskDefinition


class BaseAgentServer(MessageQueuePublisherMixin, ABC):
    @property
    @abstractmethod
    def agent_definition(self) -> AgentDefinition:
        """Get the agent definition."""
        ...

    @abstractmethod
    async def start_processing_loop(self) -> None:
        """The main processing loop of the agent server."""
        ...

    @abstractmethod
    def launch(self) -> None:
        """Launch the agent server."""
        ...

    @abstractmethod
    def get_consumer(self) -> BaseMessageQueueConsumer:
        """Get the consumer for the message queue."""
        ...

    @abstractmethod
    async def home(self) -> Dict[str, str]:
        """Get the home page of the server, usually containing status info."""
        ...

    @abstractmethod
    async def create_task(self, task_def: TaskDefinition) -> _Task:
        """Create a new task."""
        ...

    @abstractmethod
    async def get_tasks(self) -> List[_Task]:
        """Get a list of all tasks."""
        ...

    @abstractmethod
    async def get_task_state(self, task_id: str) -> _TaskSate:
        """Get a specific state of a task."""
        ...

    @abstractmethod
    async def get_completed_tasks(self) -> List[_Task]:
        """Get a list of all completed tasks."""
        ...

    @abstractmethod
    async def get_task_output(self, task_id: str) -> _TaskStepOutput:
        """Get the output of a task."""
        ...

    @abstractmethod
    async def get_task_steps(self, task_id: str) -> List[_TaskStep]:
        """Get the steps of a task."""
        ...

    @abstractmethod
    async def get_completed_steps(self, task_id: str) -> List[_TaskStepOutput]:
        """Get the completed steps of a task."""
        ...
