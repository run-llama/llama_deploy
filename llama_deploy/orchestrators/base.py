from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

from llama_deploy.messages.base import QueueMessage
from llama_deploy.types import TaskDefinition, TaskResult


class BaseOrchestrator(ABC):
    """Base class for an orchestrator.

    The general idea for an orchestrator is to manage the flow of messages between services.

    Given some state, and task, figure out the next messages to publish. Then, once
    the messages are processed, update the state with the results.
    """

    @abstractmethod
    async def get_next_messages(
        self, task_def: TaskDefinition, state: Dict[str, Any]
    ) -> Tuple[List[QueueMessage], Dict[str, Any]]:
        """Get the next message to process. Returns the message and the new state."""
        ...

    @abstractmethod
    async def add_result_to_state(
        self, result: TaskResult, state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add the result of processing a message to the state. Returns the new state."""
        ...
