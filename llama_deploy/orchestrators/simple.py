import json
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Any, Dict, List, Optional, Tuple


from llama_deploy.messages.base import QueueMessage
from llama_deploy.orchestrators.base import BaseOrchestrator
from llama_deploy.orchestrators.utils import get_result_key
from llama_deploy.types import ActionTypes, TaskDefinition, TaskResult


class SimpleOrchestratorConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SIMPLE_ORCHESTRATOR_")

    max_retries: int = 3
    final_message_type: Optional[str] = None


class SimpleOrchestrator(BaseOrchestrator):
    """A simple orchestrator that handles orchestration between a service and a user.

    Currently, the final message is published to the `human` message queue for final processing.
    """

    def __init__(self, max_retries: int = 3, final_message_type: str = "human") -> None:
        self.max_retries = max_retries
        self.final_message_type = final_message_type

    async def get_next_messages(
        self, task_def: TaskDefinition, state: Dict[str, Any]
    ) -> Tuple[List[QueueMessage], Dict[str, Any]]:
        """Get the next message to process. Returns the message and the new state.

        Assumes the agent_id (i.e. the service name) is the destination for the next message.

        Runs the required service, then sends the result to the final message type.
        """

        destination_messages = []

        if task_def.agent_id is None:
            raise ValueError(
                "Task definition must have an agent_id specified as a service name"
            )

        if task_def.task_id not in state:
            state[task_def.task_id] = {}

        result_key = get_result_key(task_def.task_id)
        if state.get(result_key, None) is not None:
            result = state[result_key]
            if not isinstance(result, TaskResult):
                if isinstance(result, str):
                    result = TaskResult(**json.loads(result))
                elif isinstance(result, dict):
                    result = TaskResult(**result)
                else:
                    raise ValueError(f"Result must be a TaskResult, not {type(result)}")

            assert isinstance(result, TaskResult), "Result must be a TaskResult"

            if self.final_message_type is not None:
                destination = self.final_message_type

                destination_messages = [
                    QueueMessage(
                        type=destination,
                        action=ActionTypes.COMPLETED_TASK,
                        data=result.model_dump(),
                    )
                ]
        else:
            destination = task_def.agent_id
            destination_messages = [
                QueueMessage(
                    type=destination,
                    action=ActionTypes.NEW_TASK,
                    data=task_def.model_dump(),
                )
            ]

        return destination_messages, state

    async def add_result_to_state(
        self, result: TaskResult, state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add the result of processing a message to the state. Returns the new state."""

        # TODO: detect failures + retries
        cur_retries = state.get("retries", -1) + 1
        state["retries"] = cur_retries

        # add result to state
        state[get_result_key(result.task_id)] = result

        return state
