from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

from llama_index.core.tools import BaseTool

from llama_agents.messages.base import QueueMessage
from llama_agents.types import TaskDefinition, TaskResult


class BaseOrchestrator(ABC):
    @abstractmethod
    async def get_next_messages(
        self, task_def: TaskDefinition, tools: List[BaseTool], state: Dict[str, Any]
    ) -> Tuple[List[QueueMessage], Dict[str, Any]]:
        """Get the next message to process. Returns the message and the new state."""
        ...

    @abstractmethod
    async def add_result_to_state(
        self, result: TaskResult, state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add the result of processing a message to the state. Returns the new state."""
        ...
