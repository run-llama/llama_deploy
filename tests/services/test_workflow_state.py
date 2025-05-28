from llama_deploy.services.workflow import (
    WorkflowState,
)


def test_workflow_state_creation() -> None:
    """Test basic workflow state creation."""
    state = WorkflowState(task_id="test_task")
    assert state.task_id == "test_task"
    assert state.hash is None
    assert state.state == {}
    assert state.run_kwargs == {}
    assert state.session_id is None


def test_workflow_state_with_data() -> None:
    """Test workflow state with full data."""
    state = WorkflowState(
        task_id="test_task",
        hash="test_hash",
        state={"key": "value"},
        run_kwargs={"param": "value"},
        session_id="test_session",
    )
    assert state.task_id == "test_task"
    assert state.hash == "test_hash"
    assert state.state == {"key": "value"}
    assert state.run_kwargs == {"param": "value"}
    assert state.session_id == "test_session"


def test_workflow_state_json_serialization() -> None:
    """Test JSON serialization/deserialization."""
    state = WorkflowState(
        task_id="test_task", state={"key": "value"}, run_kwargs={"param": "value"}
    )
    json_str = state.model_dump_json()
    deserialized = WorkflowState.model_validate_json(json_str)
    assert deserialized.task_id == state.task_id
    assert deserialized.state == state.state
    assert deserialized.run_kwargs == state.run_kwargs
