from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

from agentfile.messages.base import QueueMessage
from agentfile.types import TaskDefinition, TaskResult


class BaseOrchestrator(ABC):
    @abstractmethod
    async def get_next_messages(
        self, task_def: TaskDefinition, state: Dict[str, Any]
    ) -> Tuple[List[QueueMessage], Dict[str, Any]]:
        """Get the next message to process. Returns the message and the new state."""
        ...

    @abstractmethod
    async def add_result_to_state(
        self, state: Dict[str, Any], result: TaskResult
    ) -> Dict[str, Any]:
        """Add the result of processing a message to the state. Returns the new state."""
        ...
