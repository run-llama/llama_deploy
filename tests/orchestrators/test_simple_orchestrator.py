import pytest

from llama_deploy.orchestrators.simple import SimpleOrchestrator
from llama_deploy.messages.base import QueueMessage
from llama_deploy.orchestrators.simple import get_result_key
from llama_deploy.types import (
    ActionTypes,
    TaskDefinition,
    TaskResult,
    SessionDefinition,
)

TASK_DEF = TaskDefinition(
    input="Tell me a secret fact.",
    service_id="secret_fact_agent",
    session_id="session_id",
)

SESSION_DEF = SessionDefinition(
    task_ids=[TASK_DEF.task_id],
    session_id="session_id",
    state={},
)

INITIAL_QUEUE_MESSAGE = QueueMessage(
    type="secret_fact_agent",
    data=TASK_DEF.model_dump(),
    action=ActionTypes.NEW_TASK,
)


@pytest.mark.asyncio()
async def test_get_next_message() -> None:
    orchestrator = SimpleOrchestrator()

    queue_messages, state = await orchestrator.get_next_messages(
        TASK_DEF,
        SESSION_DEF.state,
    )

    assert len(queue_messages) == 1
    assert queue_messages[0].type == INITIAL_QUEUE_MESSAGE.type
    assert isinstance(queue_messages[0].data, dict)
    assert queue_messages[0].data["input"] == INITIAL_QUEUE_MESSAGE.data["input"]  # type: ignore

    assert state[TASK_DEF.task_id] == {}


@pytest.mark.asyncio()
async def test_add_result_to_state() -> None:
    orchestrator = SimpleOrchestrator()

    _, state = await orchestrator.get_next_messages(
        TASK_DEF,
        SESSION_DEF.state,
    )

    new_state = await orchestrator.add_result_to_state(
        TaskResult(
            task_id=TASK_DEF.task_id,
            result="The secret fact is: A Cria is a baby llama.",
            history=[],
        ),
        state,
    )

    assert "retries" in new_state
    assert new_state["retries"] == 0

    assert get_result_key(TASK_DEF.task_id) in new_state
    result = new_state[get_result_key(TASK_DEF.task_id)]

    assert isinstance(result, TaskResult)
    assert result.task_id == TASK_DEF.task_id
    assert result.result == "The secret fact is: A Cria is a baby llama."
    assert result.history == []
