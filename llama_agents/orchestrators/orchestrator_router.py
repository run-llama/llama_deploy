from typing import Any, Dict, List, Tuple

from llama_index.core.tools import BaseTool
from llama_index.core.base.base_selector import BaseSelector

from llama_agents.messages.base import QueueMessage
from llama_agents.orchestrators.base import BaseOrchestrator
from llama_agents.types import TaskDefinition, TaskResult

import logging

logger = logging.getLogger(__name__)


class OrchestratorRouter(BaseOrchestrator):
    """Orchestrator that routes between a list of orchestrators.

    Given an incoming task, first select the most relevant orchestrator to the
    task, and then use that orchestrator to process it.

    Attributes:
        orchestrators (List[BaseOrchestrator]): The orchestrators to choose from. (must correspond to choices)
        choices (List[str]): The descriptions of the orchestrators (must correspond to components)
        selector (BaseSelector): The orchestrator selector.

    Examples:
        ```python
        from llama_index.core.query_pipeline import QueryPipeline
        from llama_agents import (
            PipelineOrchestrator,
            RouterOrchestrator,
            AgentService,
            ServiceComponent
        )

        query_rewrite_server = AgentService(
            agent=hyde_agent,
            message_queue=message_queue,
            description="Used to rewrite queries",
            service_name="query_rewrite_agent",
            host="127.0.0.1",
            port=8011,
        )
        query_rewrite_server_c = ServiceComponent.from_service_definition(query_rewrite_server)

        rag_agent_server = AgentService(
            agent=rag_agent,
            message_queue=message_queue,
            description="rag_agent",
            host="127.0.0.1",
            port=8012,
        )
        rag_agent_server_c = ServiceComponent.from_service_definition(rag_agent_server)

        # create our multi-agent framework components
        pipeline_1 = QueryPipeline(chain=[query_rewrite_server_c])
        orchestrator_1 = PipelineOrchestrator(pipeline=pipeline_1)

        pipeline_2 = QueryPipeline(chain=[rag_agent_server_c])
        orchestrator_2 = PipelineOrchestrator(pipeline=pipeline_2)

        orchestrator = RouterOrchestrator(
            selector=PydanticSingleSelector.from_defaults(llm=OpenAI()),
            orchestrators=[orchestrator_1, orchestrator_2],
            choices=["description of orchestrator_1", "description of orchestrator_2"],
        )
    """

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

    async def _select_orchestrator(self, task_def: TaskDefinition) -> BaseOrchestrator:
        if task_def.task_id not in self.tasks:
            sel_output = await self.selector.aselect(self.choices, task_def.input)
            self.tasks[task_def.task_id] = sel_output.ind
            # assume one selection
            if len(sel_output.selections) != 1:
                raise ValueError("Expected one selection")
            logger.info("Selected orchestrator for task.")
        return self.orchestrators[self.tasks[task_def.task_id]]

    async def get_next_messages(
        self, task_def: TaskDefinition, tools: List[BaseTool], state: Dict[str, Any]
    ) -> Tuple[List[QueueMessage], Dict[str, Any]]:
        """Get the next message to process. Returns the message and the new state."""
        orchestrator = await self._select_orchestrator(task_def)
        return await orchestrator.get_next_messages(task_def, tools, state)

    async def add_result_to_state(
        self, result: TaskResult, state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add the result of processing a message to the state. Returns the new state.

        TODO: figure out a way to properly clear the tasks dictionary when the
        highest level Task is actually completed.
        """
        if result.task_id not in self.tasks:
            raise ValueError("Task not found.")
        orchestrator = self.orchestrators[self.tasks[result.task_id]]
        res = await orchestrator.add_result_to_state(result, state)
        return res
