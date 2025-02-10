from unittest import mock

import pytest
from llama_index.core.workflow import StartEvent

from llama_deploy import ControlPlaneConfig
from llama_deploy.deploy.network_workflow import (
    NetworkServiceManager,
    NetworkWorkflow,
    ServiceNotFoundError,
)


def test_network_workflow_ctor() -> None:
    nw = NetworkWorkflow(remote_service_name="test_workflow")
    assert nw.remote_service_name == "test_workflow"

    with pytest.warns(
        DeprecationWarning, match="The control_plane_config parameter is deprecated"
    ):
        nw = NetworkWorkflow(
            remote_service_name="test_workflow",
            control_plane_config=ControlPlaneConfig(),
        )
    assert nw.remote_service_name == "test_workflow"


@pytest.mark.asyncio
async def test_network_workflow_run_remote_workflow() -> None:
    # Setup
    mock_client = mock.MagicMock()
    mock_session = mock.MagicMock()
    mock_session.run = mock.AsyncMock(return_value={"result": "success"})
    mock_session.id = "test_session_id"

    mock_client.core.sessions.create = mock.AsyncMock(return_value=mock_session)
    mock_client.core.sessions.delete = mock.AsyncMock()

    # Create workflow
    workflow = NetworkWorkflow(remote_service_name="test_workflow")
    workflow._client = mock_client  # Inject mock client

    # Create start event with test data
    start_event = StartEvent(param1="value1", param2="value2")  # type:ignore

    # Run workflow
    result = await workflow.run_remote_workflow(start_event)

    # Assertions
    assert result.result == {"result": "success"}
    mock_client.core.sessions.create.assert_awaited_once()
    mock_session.run.assert_awaited_once_with(
        "test_workflow", param1="value1", param2="value2"
    )
    mock_client.core.sessions.delete.assert_awaited_once_with("test_session_id")


def test_service_manager_ctor() -> None:
    sm = NetworkServiceManager()
    assert not sm._services

    with pytest.warns(
        DeprecationWarning, match="The control_plane_config parameter is deprecated"
    ):
        NetworkServiceManager(control_plane_config=ControlPlaneConfig())


def test_service_manager_get() -> None:
    mock_client = mock.MagicMock()
    mock_service = mock.MagicMock()
    mock_service.service_name = "test_service"

    # Mock the client.sync.core.services.list() call
    mock_client.sync.core.services.list.return_value = [mock_service]

    # Create service manager with some existing services
    existing_services = {"local_service": mock.MagicMock()}
    sm = NetworkServiceManager(existing_services=existing_services)  # type: ignore
    sm._client = mock_client  # Inject mock client

    # Test getting existing local service
    local_workflow = sm.get("local_service")
    assert local_workflow == existing_services["local_service"]

    # Test getting remote service
    remote_workflow = sm.get("test_service")
    assert isinstance(remote_workflow, NetworkWorkflow)
    assert remote_workflow.remote_service_name == "test_service"
    assert remote_workflow._timeout == remote_workflow._client.timeout
    assert remote_workflow._timeout is None

    # Test service not found
    with pytest.raises(
        ServiceNotFoundError, match="Service nonexistent_service not found"
    ):
        sm.get("nonexistent_service")

    # Verify client method was called
    mock_client.sync.core.services.list.assert_called()
