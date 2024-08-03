from typing import Any, Dict, List, Tuple

from llama_index.core.tools import BaseTool
from llama_index.core.base.base_selector import BaseSelector

from llama_agents.messages.base import QueueMessage
from llama_agents.orchestrators.base import BaseOrchestrator
from llama_agents.types import TaskDefinition, TaskResult

import logging

logger = logging.getLogger(__name__)


class RouterOrchestrator(BaseOrchestrator):
    """Orchestrator that routes between a list of pipeline orchestrators."""

    def __init__(
        self,
        orchestrators: List[BaseOrchestrator],
        choices: List[str],
        selector: BaseSelector,
    ):
        self.orchestrators = orchestrators
        self.choices = choices
        self.selector = selector
        self.tasks: Dict[str, int] = {}

    def _select_orchestrator(self, task_def: TaskDefinition) -> BaseOrchestrator:
        sel_output = self.selector.select(self.choices, task_def.input)
        # assume one selection
        if len(sel_output.selections) != 1:
            raise ValueError("Expected one selection")
        self.tasks[task_def.task_id] = sel_output.ind
        return self.orchestrators[sel_output.ind]

    async def get_next_messages(
        self, task_def: TaskDefinition, tools: List[BaseTool], state: Dict[str, Any]
    ) -> Tuple[List[QueueMessage], Dict[str, Any]]:
        orchestrator = self._select_orchestrator(task_def)
        return await orchestrator.get_next_messages(task_def, tools, state)

    async def add_result_to_state(
        self, result: TaskResult, state: Dict[str, Any]
    ) -> Dict[str, Any]:
        if result.task_id not in self.tasks:
            raise ValueError("Task not found.")
        orchestrator = self.orchestrators[self.tasks[result.task_id]]
        return await orchestrator.add_result_to_state(result, state)
