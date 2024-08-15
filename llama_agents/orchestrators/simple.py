import json
from typing import Any, Dict, List, Tuple

from llama_index.core.tools import BaseTool

from llama_agents.messages.base import QueueMessage
from llama_agents.orchestrators.base import BaseOrchestrator
from llama_agents.types import ActionTypes, TaskDefinition, TaskResult


class SimpleOrchestrator(BaseOrchestrator):
    """A simple orchestrator that handles orchestration between a service and a user.

    Currently, the final message is published to the `human` message queue for final processing.
    """

    def __init__(self, max_retries: int = 3, final_message_type: str = "human") -> None:
        self.max_retries = max_retries
        self.final_message_type = final_message_type

    async def get_next_messages(
        self, task_def: TaskDefinition, tools: List[BaseTool], state: Dict[str, Any]
    ) -> Tuple[List[QueueMessage], Dict[str, Any]]:
        """Get the next message to process. Returns the message and the new state.

        Assumes the agent_id (i.e. the service name) is the destination for the next message.

        Runs the required service, then sends the result to the final message type.
        """

        if state.get("result", None) is not None:
            result = state["result"]
            if not isinstance(result, TaskResult):
                if isinstance(result, str):
                    result = TaskResult(**json.loads(result))
                elif isinstance(result, dict):
                    result = TaskResult(**result)
                else:
                    raise ValueError(f"Result must be a TaskResult, not {type(result)}")

            assert isinstance(result, TaskResult), "Result must be a TaskResult"

            destination = self.final_message_type
            destination_message = QueueMessage(
                type=destination,
                action=ActionTypes.COMPLETED_TASK,
                data=result.model_dump(),
            )
        else:
            assert (
                task_def.agent_id is not None
            ), "Task definition must have an agent_id"

            destination = task_def.agent_id
            destination_message = QueueMessage(
                type=destination,
                action=ActionTypes.NEW_TASK,
                data=task_def.model_dump(),
            )

        return [destination_message], state

    async def add_result_to_state(
        self, result: TaskResult, state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add the result of processing a message to the state. Returns the new state."""

        # TODO: detect failures + retries
        cur_retries = state.get("retries", 0) + 1
        state["retries"] = cur_retries
        state["result"] = result

        return state
