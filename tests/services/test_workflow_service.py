import asyncio
import json
from typing import AsyncIterator
from unittest import mock

import httpx
import pytest
from llama_index.core.workflow import Context, Workflow
from llama_index.core.workflow.events import Event
from llama_index.core.workflow.handler import WorkflowHandler

from llama_deploy.message_queues.base import AbstractMessageQueue
from llama_deploy.messages.base import QueueMessage
from llama_deploy.services.workflow import (
    WorkflowService,
    WorkflowServiceConfig,
    WorkflowState,
    _make_hash,
)
from llama_deploy.types import ActionTypes, ServiceDefinition, TaskDefinition


@pytest.fixture
def mock_workflow() -> Workflow:
    """Create a mock workflow."""
    workflow = mock.MagicMock(spec=Workflow)
    return workflow


@pytest.fixture
def mock_message_queue() -> AbstractMessageQueue:
    """Create a mock message queue."""
    queue = mock.MagicMock(spec=AbstractMessageQueue)
    queue.publish = mock.AsyncMock()
    queue.get_message = mock.AsyncMock()
    return queue


@pytest.fixture
def config() -> WorkflowServiceConfig:
    """Create a test config."""
    return WorkflowServiceConfig(
        host="localhost", port=8000, service_name="test_workflow_service"
    )


@pytest.fixture
def workflow_service(
    mock_workflow: Workflow,
    mock_message_queue: AbstractMessageQueue,
    config: WorkflowServiceConfig,
) -> WorkflowService:
    """Create a WorkflowService instance for testing."""
    return WorkflowService(
        workflow=mock_workflow, message_queue=mock_message_queue, config=config
    )


def test_make_hash_basic() -> None:
    """Test basic hash generation."""
    result = _make_hash("test_context")
    assert isinstance(result, str)
    assert len(result) == 64  # SHA256 hex digest length


def test_make_hash_consistency() -> None:
    """Test that same input produces same hash."""
    context_str = "test_context"
    hash1 = _make_hash(context_str)
    hash2 = _make_hash(context_str)
    assert hash1 == hash2


def test_make_hash_different_inputs() -> None:
    """Test that different inputs produce different hashes."""
    hash1 = _make_hash("context1")
    hash2 = _make_hash("context2")
    assert hash1 != hash2


@mock.patch.dict("os.environ", {"LLAMA_DEPLOY_WF_SERVICE_HASH_SECRET": "test_secret"})
def test_make_hash_with_custom_secret() -> None:
    """Test hash generation with custom secret."""
    result = _make_hash("test_context")
    assert isinstance(result, str)
    assert len(result) == 64


def test_init(
    workflow_service: WorkflowService,
    mock_workflow: Workflow,
    mock_message_queue: AbstractMessageQueue,
    config: WorkflowServiceConfig,
) -> None:
    """Test WorkflowService initialization."""
    assert workflow_service.workflow == mock_workflow
    assert workflow_service.config == config
    assert workflow_service._message_queue == mock_message_queue
    assert workflow_service._service_name == "test_workflow_service"
    assert isinstance(workflow_service._lock, asyncio.Lock)
    assert workflow_service._running is True
    assert isinstance(workflow_service._publisher_id, str)
    assert workflow_service._publish_callback is None
    assert workflow_service._outstanding_calls == {}
    assert workflow_service._ongoing_tasks == {}


def test_service_name_property(workflow_service: WorkflowService) -> None:
    """Test service_name property."""
    assert workflow_service.service_name == "test_workflow_service"


def test_service_definition_property(workflow_service: WorkflowService) -> None:
    """Test service_definition property."""
    definition = workflow_service.service_definition
    assert isinstance(definition, ServiceDefinition)
    assert definition.service_name == "test_workflow_service"
    assert definition.host == "localhost"
    assert definition.port == 8000


def test_message_queue_property(
    workflow_service: WorkflowService, mock_message_queue: AbstractMessageQueue
) -> None:
    """Test message_queue property."""
    assert workflow_service.message_queue == mock_message_queue


def test_publisher_id_property(workflow_service: WorkflowService) -> None:
    """Test publisher_id property."""
    publisher_id = workflow_service.publisher_id
    assert isinstance(publisher_id, str)
    assert publisher_id.startswith("WorkflowService-")


def test_publish_callback_property(workflow_service: WorkflowService) -> None:
    """Test publish_callback property."""
    assert workflow_service.publish_callback is None


def test_lock_property(workflow_service: WorkflowService) -> None:
    """Test lock property."""
    assert isinstance(workflow_service.lock, asyncio.Lock)


def test_get_topic(workflow_service: WorkflowService) -> None:
    """Test get_topic method."""
    topic = workflow_service.get_topic("test_type")
    assert topic == "llama_deploy.test_type"


@pytest.mark.asyncio
async def test_get_workflow_state_no_session_id(
    workflow_service: WorkflowService,
) -> None:
    """Test get_workflow_state with no session_id."""
    state = WorkflowState(task_id="test_task")
    result = await workflow_service.get_workflow_state(state)
    assert result is None


@pytest.mark.asyncio
async def test_get_workflow_state_no_session_state(
    workflow_service: WorkflowService,
) -> None:
    """Test get_workflow_state when session state doesn't exist."""
    state = WorkflowState(task_id="test_task", session_id="test_session")

    with mock.patch.object(workflow_service, "get_session_state", return_value=None):
        result = await workflow_service.get_workflow_state(state)
        assert result is None


@pytest.mark.asyncio
async def test_get_workflow_state_no_workflow_state(
    workflow_service: WorkflowService,
) -> None:
    """Test get_workflow_state when workflow state doesn't exist in session."""
    state = WorkflowState(task_id="test_task", session_id="test_session")
    session_state = {"other_session": "data"}

    with mock.patch.object(
        workflow_service, "get_session_state", return_value=session_state
    ):
        result = await workflow_service.get_workflow_state(state)
        assert result is None


@pytest.mark.asyncio
async def test_get_workflow_state_success(
    workflow_service: WorkflowService, mock_workflow: Workflow
) -> None:
    """Test successful get_workflow_state."""
    test_state_dict = {"key": "value"}
    test_hash = _make_hash(json.dumps(test_state_dict))

    workflow_state = WorkflowState(
        task_id="test_task",
        session_id="test_session",
        hash=test_hash,
        state=test_state_dict,
    )

    session_state = {"test_session": workflow_state.model_dump_json()}

    mock_context = mock.MagicMock(spec=Context)

    with (
        mock.patch.object(
            workflow_service, "get_session_state", return_value=session_state
        ),
        mock.patch.object(
            Context, "from_dict", return_value=mock_context
        ) as mock_from_dict,
    ):
        result = await workflow_service.get_workflow_state(
            WorkflowState(task_id="test_task", session_id="test_session")
        )

        assert result == mock_context
        mock_from_dict.assert_called_once_with(
            mock_workflow, test_state_dict, serializer=mock.ANY
        )


@pytest.mark.asyncio
async def test_get_workflow_state_hash_mismatch(
    workflow_service: WorkflowService,
) -> None:
    """Test get_workflow_state with hash mismatch."""
    test_state_dict = {"key": "value"}
    wrong_hash = "wrong_hash"

    workflow_state = WorkflowState(
        task_id="test_task",
        session_id="test_session",
        hash=wrong_hash,
        state=test_state_dict,
    )

    session_state = {"test_session": workflow_state.model_dump_json()}

    with mock.patch.object(
        workflow_service, "get_session_state", return_value=session_state
    ):
        with pytest.raises(ValueError, match="Context hash does not match!"):
            await workflow_service.get_workflow_state(
                WorkflowState(task_id="test_task", session_id="test_session")
            )


@pytest.mark.asyncio
async def test_set_workflow_state_no_session_id(
    workflow_service: WorkflowService,
) -> None:
    """Test set_workflow_state with no session_id."""
    mock_context = mock.MagicMock(spec=Context)
    mock_context.to_dict.return_value = {"key": "value"}

    current_state = WorkflowState(task_id="test_task")

    with pytest.raises(
        ValueError, match="Session ID is None! Cannot set workflow state."
    ):
        await workflow_service.set_workflow_state(mock_context, current_state)


@pytest.mark.asyncio
async def test_set_workflow_state_success(workflow_service: WorkflowService) -> None:
    """Test successful set_workflow_state."""
    test_state_dict = {"key": "value"}
    mock_context = mock.MagicMock(spec=Context)
    mock_context.to_dict.return_value = test_state_dict

    current_state = WorkflowState(
        task_id="test_task",
        session_id="test_session",
        run_kwargs={"param": "value"},
    )

    existing_session_state = {"existing": "data"}

    with (
        mock.patch.object(
            workflow_service,
            "get_session_state",
            return_value=existing_session_state,
        ) as mock_get,
        mock.patch.object(workflow_service, "update_session_state") as mock_update,
    ):
        await workflow_service.set_workflow_state(mock_context, current_state)

        mock_get.assert_called_once_with("test_session")
        mock_update.assert_called_once()

        # Check that the session state was updated correctly
        call_args = mock_update.call_args[0]
        assert call_args[0] == "test_session"
        updated_state = call_args[1]
        assert "test_session" in updated_state


@pytest.mark.asyncio
async def test_process_call_success(
    workflow_service: WorkflowService, mock_workflow: Workflow
) -> None:
    """Test successful process_call."""
    # Mock workflow handler
    mock_handler = mock.AsyncMock(spec=WorkflowHandler)
    mock_handler.ctx = mock.MagicMock(spec=Context)
    # mock_handler.__aiter__ = mock.AsyncMock(return_value=iter([]))
    mock_handler.stream_events = mock.AsyncMock(
        return_value=mock.AsyncMock(__aiter__=lambda x: iter([]))
    )
    mock_handler.__await__ = lambda: iter([mock.AsyncMock()])

    # Mock workflow.run to return the handler
    mock_workflow.run.return_value = mock_handler  # type: ignore

    current_call = WorkflowState(
        task_id="test_task",
        session_id="test_session",
        run_kwargs={"param": "value"},
    )

    with (
        mock.patch.object(workflow_service, "get_workflow_state", return_value=None),
        mock.patch.object(workflow_service, "set_workflow_state") as mock_set_state,
        mock.patch.object(workflow_service.message_queue, "publish") as mock_publish,
    ):
        await workflow_service.process_call(current_call)

        # Verify workflow was run with correct parameters
        mock_workflow.run.assert_called_once_with(ctx=None, param="value")  # type: ignore

        # Verify state was set
        mock_set_state.assert_called()

        # Verify final result was published
        mock_publish.assert_called()


@pytest.mark.asyncio
async def test_process_call_exception_with_raise(
    workflow_service: WorkflowService,
    mock_workflow: Workflow,
    config: WorkflowServiceConfig,
) -> None:
    """Test process_call with exception when raise_exceptions=True."""
    config.raise_exceptions = True

    # Mock workflow.run to raise an exception
    mock_workflow.run.side_effect = ValueError("Test error")  # type: ignore

    current_call = WorkflowState(
        task_id="test_task",
        session_id="test_session",
        run_kwargs={"param": "value"},
    )

    with mock.patch.object(workflow_service, "get_workflow_state", return_value=None):
        with pytest.raises(ValueError, match="Test error"):
            await workflow_service.process_call(current_call)


@pytest.mark.asyncio
async def test_process_call_exception_without_raise(
    workflow_service: WorkflowService,
    mock_workflow: Workflow,
    config: WorkflowServiceConfig,
) -> None:
    """Test process_call with exception when raise_exceptions=False."""
    config.raise_exceptions = False

    # Mock workflow.run to raise an exception
    mock_workflow.run.side_effect = ValueError("Test error")  # type: ignore

    current_call = WorkflowState(
        task_id="test_task",
        session_id="test_session",
        run_kwargs={"param": "value"},
    )

    with (
        mock.patch.object(workflow_service, "get_workflow_state", return_value=None),
        mock.patch.object(workflow_service.message_queue, "publish") as mock_publish,
    ):
        await workflow_service.process_call(current_call)

        # Verify error was published
        mock_publish.assert_called()
        call_args = mock_publish.call_args[0][0]
        assert call_args.action == ActionTypes.COMPLETED_TASK
        assert "Test error" in call_args.data["result"]


@pytest.mark.asyncio
async def test_processing_loop(workflow_service: WorkflowService) -> None:
    """Test processing_loop method."""
    with mock.patch.object(workflow_service, "manage_tasks") as mock_manage:
        mock_manage.side_effect = asyncio.CancelledError()

        await workflow_service.processing_loop()

        mock_manage.assert_called_once()


@pytest.mark.asyncio
async def test_process_messages_new_task(workflow_service: WorkflowService) -> None:
    """Test _process_messages with NEW_TASK action."""
    task_def = TaskDefinition(
        task_id="test_task", session_id="test_session", input='{"param": "value"}'
    )

    message = QueueMessage(
        type="test_type", action=ActionTypes.NEW_TASK, data=task_def.model_dump()
    )

    # Mock the async iterator
    async def mock_get_messages(topic: str) -> AsyncIterator[QueueMessage]:
        yield message

    workflow_service._message_queue.get_messages = mock_get_messages  # type: ignore

    # Process one message
    await workflow_service._process_messages("test_topic")

    # Verify task was added to outstanding calls
    assert "test_task" in workflow_service._outstanding_calls
    call_state = workflow_service._outstanding_calls["test_task"]
    assert call_state.task_id == "test_task"
    assert call_state.session_id == "test_session"
    assert call_state.run_kwargs == {"param": "value"}


@pytest.mark.asyncio
async def test_process_messages_send_event(workflow_service: WorkflowService) -> None:
    """Test _process_messages with SEND_EVENT action."""
    # Create a test event
    test_event = Event()

    task_def = TaskDefinition(
        task_id="test_task",
        session_id="test_session",
        input=json.dumps(test_event.model_dump()),
    )

    message = QueueMessage(
        type="test_type", action=ActionTypes.SEND_EVENT, data=task_def.model_dump()
    )

    # Mock the async iterator
    async def mock_get_messages(topic: str) -> AsyncIterator[QueueMessage]:
        yield message

    workflow_service._message_queue.get_messages = mock_get_messages  # type: ignore

    # Process one message
    await workflow_service._process_messages("test_topic")

    # Verify event was added to buffer
    assert "test_task" in workflow_service._events_buffer
    assert not workflow_service._events_buffer["test_task"].empty()


@pytest.mark.asyncio
async def test_process_messages_unknown_action(
    workflow_service: WorkflowService,
) -> None:
    """Test _process_messages with unknown action."""
    message = QueueMessage(
        type="test_type", action=ActionTypes.REQUEST_FOR_HELP, data={}
    )

    # Mock the async iterator
    async def mock_get_messages(topic: str) -> AsyncIterator[QueueMessage]:
        yield message

    workflow_service._message_queue.get_messages = mock_get_messages  # type: ignore

    # Should raise ValueError for unknown action
    with pytest.raises(ValueError, match="Unhandled action"):
        await workflow_service._process_messages("test_topic")


@pytest.mark.asyncio
async def test_launch_server(workflow_service: WorkflowService) -> None:
    """Test launch_server method."""
    with (
        mock.patch.object(workflow_service, "processing_loop") as mock_processing,
        mock.patch.object(workflow_service, "_process_messages") as mock_messages,
    ):
        await workflow_service.launch_server()

        mock_processing.assert_called_once()
        mock_messages.assert_called_once()


@pytest.mark.asyncio
async def test_register_to_control_plane(workflow_service: WorkflowService) -> None:
    """Test register_to_control_plane method."""
    control_plane_url = "http://control-plane:8000"

    mock_response = mock.MagicMock()
    mock_response.json.return_value = {"topic_namespace": "test_namespace"}

    with mock.patch("httpx.AsyncClient") as mock_client:
        mock_client_instance = mock.AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        await workflow_service.register_to_control_plane(control_plane_url)

        # Verify the control plane URL was set
        assert workflow_service._control_plane_url == control_plane_url

        # Verify the registration call was made
        mock_client_instance.post.assert_called_once_with(
            f"{control_plane_url}/services/register",
            json=workflow_service.service_definition.model_dump(),
        )


@pytest.mark.asyncio
async def test_deregister_from_control_plane(workflow_service: WorkflowService) -> None:
    """Test deregister_from_control_plane method."""
    workflow_service._control_plane_url = "http://control-plane:8000"

    mock_response = mock.MagicMock()

    with mock.patch("httpx.AsyncClient") as mock_client:
        mock_client_instance = mock.AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        await workflow_service.deregister_from_control_plane()

        mock_client_instance.post.assert_called_once_with(
            "http://control-plane:8000/services/deregister",
            params={"service_name": workflow_service.service_name},
        )


@pytest.mark.asyncio
async def test_deregister_from_control_plane_no_url(
    workflow_service: WorkflowService,
) -> None:
    """Test deregister_from_control_plane without URL set."""
    workflow_service._control_plane_url = ""

    with pytest.raises(ValueError, match="Control plane URL not set"):
        await workflow_service.deregister_from_control_plane()


@pytest.mark.asyncio
async def test_get_session_state_success(workflow_service: WorkflowService) -> None:
    """Test successful get_session_state."""
    workflow_service._control_plane_url = "http://control-plane:8000"
    session_id = "test_session"
    expected_state = {"key": "value"}

    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = expected_state

    with mock.patch("httpx.AsyncClient") as mock_client:
        mock_client_instance = mock.AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        result = await workflow_service.get_session_state(session_id)

        assert result == expected_state
        mock_client_instance.get.assert_called_once_with(
            f"http://control-plane:8000/sessions/{session_id}/state"
        )


@pytest.mark.asyncio
async def test_get_session_state_not_found(workflow_service: WorkflowService) -> None:
    """Test get_session_state when session not found."""
    workflow_service._control_plane_url = "http://control-plane:8000"
    session_id = "test_session"

    mock_response = mock.MagicMock()
    mock_response.status_code = 404

    with mock.patch("httpx.AsyncClient") as mock_client:
        mock_client_instance = mock.AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        result = await workflow_service.get_session_state(session_id)

        assert result is None


@pytest.mark.asyncio
async def test_get_session_state_connection_error(
    workflow_service: WorkflowService,
) -> None:
    """Test get_session_state with connection error."""
    workflow_service._control_plane_url = "http://control-plane:8000"
    session_id = "test_session"

    with mock.patch("httpx.AsyncClient") as mock_client:
        mock_client_instance = mock.AsyncMock()
        mock_client_instance.get.side_effect = httpx.ConnectError(message="Test error")
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        result = await workflow_service.get_session_state(session_id)

        assert result is None


@pytest.mark.asyncio
async def test_update_session_state_success(workflow_service: WorkflowService) -> None:
    """Test successful update_session_state."""
    workflow_service._control_plane_url = "http://control-plane:8000"
    session_id = "test_session"
    state = {"key": "value"}

    mock_response = mock.MagicMock()

    with mock.patch("httpx.AsyncClient") as mock_client:
        mock_client_instance = mock.AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        await workflow_service.update_session_state(session_id, state)

        mock_client_instance.post.assert_called_once_with(
            f"http://control-plane:8000/sessions/{session_id}/state", json=state
        )


@pytest.mark.asyncio
async def test_update_session_state_no_url(workflow_service: WorkflowService) -> None:
    """Test update_session_state without control plane URL."""
    workflow_service._control_plane_url = ""
    session_id = "test_session"
    state = {"key": "value"}

    # Should not raise an error, just return without doing anything
    await workflow_service.update_session_state(session_id, state)


def test_workflow_service_with_publish_callback(
    mock_workflow: Workflow,
    mock_message_queue: AbstractMessageQueue,
    config: WorkflowServiceConfig,
) -> None:
    """Test WorkflowService with publish callback."""
    callback = mock.MagicMock()
    service = WorkflowService(
        workflow=mock_workflow,
        message_queue=mock_message_queue,
        config=config,
        publish_callback=callback,
    )

    assert service.publish_callback == callback
