import asyncio
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from tenacity import RetryError

from llama_deploy.apiserver.deployment import Deployment, DeploymentError, Manager
from llama_deploy.apiserver.deployment_config_parser import (
    DeploymentConfig,
)
from llama_deploy.control_plane import ControlPlaneConfig, ControlPlaneServer
from llama_deploy.message_queues import AWSMessageQueueConfig, SimpleMessageQueue


@pytest.fixture
def deployment_config() -> DeploymentConfig:
    return DeploymentConfig(  # type: ignore
        **{  # type: ignore
            "name": "test-deployment",
            "control-plane": ControlPlaneConfig(),
            "services": {},
        }
    )


def test_deployment_ctor(data_path: Path, mock_importlib: Any) -> None:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")
    with mock.patch("llama_deploy.apiserver.deployment.SOURCE_MANAGERS") as sm_dict:
        sm_dict["git"] = mock.MagicMock()
        d = Deployment(config=config, root_path=Path("."))

        sm_dict["git"].return_value.sync.assert_called_once()
        assert d.name == "TestDeployment"
        assert d.path.name == "TestDeployment"
        assert type(d._control_plane) is ControlPlaneServer
        assert len(d._workflow_services) == 1
        assert d.service_names == ["test-workflow"]
        assert d.client is not None
        assert d.default_service is None


def test_deployment_ctor_missing_service_path(data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")
    config.services["test-workflow"].path = None
    with pytest.raises(
        ValueError, match="path field in service definition must be set"
    ):
        Deployment(config=config, root_path=Path("."))


def test_deployment_ctor_missing_service_port(data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")
    config.services["test-workflow"].port = None
    with pytest.raises(
        ValueError, match="port field in service definition must be set"
    ):
        Deployment(config=config, root_path=Path("."))


def test_deployment_ctor_missing_service_host(data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")
    config.services["test-workflow"].host = None
    with pytest.raises(
        ValueError, match="host field in service definition must be set"
    ):
        Deployment(config=config, root_path=Path("."))


def test_deployment_ctor_skip_default_service(
    data_path: Path, mock_importlib: Any
) -> None:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")
    config.services["test-workflow2"] = deepcopy(config.services["test-workflow"])
    config.services["test-workflow2"].source = None

    with mock.patch("llama_deploy.apiserver.deployment.SOURCE_MANAGERS") as sm_dict:
        sm_dict["git"] = mock.MagicMock()
        d = Deployment(config=config, root_path=Path("."))
        assert len(d._workflow_services) == 1


def test_deployment_ctor_invalid_default_service(
    data_path: Path, mock_importlib: Any, caplog: Any
) -> None:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")
    config.default_service = "does-not-exist"

    d = Deployment(config=config, root_path=Path("."))
    assert d.default_service is None
    assert (
        "There is no service with id 'does-not-exist' in this deployment, cannot set default."
        in caplog.text
    )


def test_deployment_ctor_default_service(data_path: Path, mock_importlib: Any) -> None:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")
    config.default_service = "test-workflow"

    d = Deployment(config=config, root_path=Path("."))
    assert d.default_service == "test-workflow"


def test_deployment___load_message_queue_default(mocked_deployment: Deployment) -> None:
    q = mocked_deployment._load_message_queue_client(None)
    assert type(q) is SimpleMessageQueue
    assert q._config.port == 8001
    assert q._config.host == "127.0.0.1"


def test_deployment___load_message_queue_not_supported(
    mocked_deployment: Deployment,
) -> None:
    mocked_config = mock.MagicMock(queue_type="does_not_exist")
    with pytest.raises(ValueError, match="Unsupported message queue:"):
        mocked_deployment._load_message_queue_client(mocked_config)


def test_deployment__load_message_queues(mocked_deployment: Deployment) -> None:
    with mock.patch("llama_deploy.apiserver.deployment.AWSMessageQueue") as m:
        mocked_config = mock.MagicMock(type="aws")
        mocked_config.model_dump.return_value = {"foo": "aws"}
        mocked_deployment._load_message_queue_client(mocked_config)
        m.assert_called_with(mocked_config)

    with mock.patch("llama_deploy.apiserver.deployment.KafkaMessageQueue") as m:
        mocked_config = mock.MagicMock(type="kafka")
        mocked_config.model_dump.return_value = {"foo": "kafka"}
        mocked_deployment._load_message_queue_client(mocked_config)
        m.assert_called_with(mocked_config)

    with mock.patch("llama_deploy.apiserver.deployment.RabbitMQMessageQueue") as m:
        mocked_config = mock.MagicMock(type="rabbitmq")
        mocked_config.model_dump.return_value = {"foo": "rabbitmq"}
        mocked_deployment._load_message_queue_client(mocked_config)
        m.assert_called_with(mocked_config)

    with mock.patch("llama_deploy.apiserver.deployment.RedisMessageQueue") as m:
        mocked_config = mock.MagicMock(type="redis")
        mocked_config.model_dump.return_value = {"foo": "redis"}
        mocked_deployment._load_message_queue_client(mocked_config)
        m.assert_called_with(mocked_config)


def test__install_dependencies(data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "python_dependencies.yaml")
    service_config = config.services["myworkflow"]
    with mock.patch("llama_deploy.apiserver.deployment.subprocess") as mocked_subp:
        # Assert the sub process cmd receives the list of dependencies
        Deployment._install_dependencies(service_config)
        mocked_subp.check_call.assert_called_with(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "llama-index-core<1",
                "llama-index-llms-openai",
            ]
        )

        # Assert the method doesn't do anything if the list of dependencies is empty
        mocked_subp.reset_mock()
        service_config.python_dependencies = []
        Deployment._install_dependencies(service_config)
        mocked_subp.check_call.assert_not_called()


def test__set_environment_variables(data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "env_variables.yaml")
    service_config = config.services["myworkflow"]
    with mock.patch("llama_deploy.apiserver.deployment.os.environ") as mocked_osenviron:
        # Assert the sub process cmd receives the list of dependencies
        Deployment._set_environment_variables(service_config, root=data_path)
        mocked_osenviron.__setitem__.assert_has_calls(
            [
                mock.call("VAR_1", "x"),
                mock.call("VAR_2", "y"),
                mock.call("API_KEY", "123"),
            ]
        )


def test__install_dependencies_raises(data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "python_dependencies.yaml")
    service_config = config.services["myworkflow"]
    error_class = subprocess.CalledProcessError
    error = error_class(1, "cmd", output=None, stderr="There was an error")
    with mock.patch("llama_deploy.apiserver.deployment.subprocess") as mocked_subp:
        # Assert the proper exception is raised if the sub process errors out
        mocked_subp.CalledProcessError = error_class
        mocked_subp.check_call.side_effect = error
        with pytest.raises(
            DeploymentError,
            match="Unable to install service dependencies using command 'cmd': There was an error",
        ):
            Deployment._install_dependencies(service_config)


def test_manager_ctor() -> None:
    m = Manager()
    assert str(m._deployments_path) == ".deployments"
    assert len(m._deployments) == 0
    m = Manager(deployments_path=Path("foo"))
    assert str(m._deployments_path) == "foo"
    assert len(m._deployments) == 0
    assert len(m.deployment_names) == 0
    assert m.get_deployment("foo") is None
    assert m._simple_message_queue_server is None


@pytest.mark.asyncio
async def test_manager_deploy_duplicate(data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")

    m = Manager()
    m._deployments["TestDeployment"] = mock.MagicMock()

    with pytest.raises(ValueError, match="Deployment already exists: TestDeployment"):
        await m.deploy(config)


@pytest.mark.asyncio
async def test_manager_deploy_maximum_reached(data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")

    m = Manager(max_deployments=1)
    m._deployments["AnotherDeployment"] = mock.MagicMock()

    with pytest.raises(
        ValueError,
        match="Reached the maximum number of deployments, cannot schedule more",
    ):
        await m.deploy(config)


@pytest.mark.asyncio
async def test_manager_deploy(data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")
    # Do not use SimpleMessageQueue here, to avoid starting the server
    config.message_queue = AWSMessageQueueConfig()

    with mock.patch(
        "llama_deploy.apiserver.deployment.Deployment"
    ) as mocked_deployment:
        m = Manager()
        await m.deploy(config)
        mocked_deployment.assert_called_once()
        assert m.deployment_names == ["TestDeployment"]
        assert m.get_deployment("TestDeployment") is not None


@pytest.mark.asyncio
async def test_manager_serve_loop() -> None:
    m = Manager()
    serve_task = asyncio.create_task(m.serve())
    # Allow the serve task to start
    await asyncio.sleep(0)

    # Check that the task is still running
    assert not serve_task.done()

    # Cancel the task
    serve_task.cancel()
    await serve_task
    assert serve_task.done()
    assert serve_task.exception() is None


def test_manager_assign_control_plane_port(data_path: Path) -> None:
    m = Manager()
    config = DeploymentConfig.from_yaml(data_path / "service_ports.yaml")
    m._assign_control_plane_address(config)
    assert config.services["no-port"].port == 8002
    assert config.services["has-port"].port == 9999
    assert config.services["no-port-again"].port == 8003


@pytest.mark.asyncio
async def test_start_control_plane_success(deployment_config: DeploymentConfig) -> None:
    # Create deployment instance
    deployment = Deployment(config=deployment_config, root_path=Path("/tmp"))

    # Mock control plane methods
    deployment._control_plane.register_to_message_queue = mock.AsyncMock(  # type: ignore
        return_value=mock.AsyncMock()
    )
    deployment._control_plane.launch_server = mock.AsyncMock()  # type: ignore

    # Mock httpx client
    mock_response = mock.MagicMock()
    mock_response.raise_for_status = mock.MagicMock()

    mock_client = mock.AsyncMock()
    mock_client.__aenter__.return_value.get.return_value = mock_response

    with mock.patch("httpx.AsyncClient", return_value=mock_client):
        # Run the method
        tasks = await deployment._start_control_plane()

        # Verify tasks were created
        assert len(tasks) == 2
        assert all(isinstance(task, asyncio.Task) for task in tasks)

        # Verify control plane methods were called
        deployment._control_plane.register_to_message_queue.assert_called_once()
        deployment._control_plane.launch_server.assert_called_once()

        # Verify health check was performed
        mock_client.__aenter__.return_value.get.assert_called_with(
            deployment_config.control_plane.url
        )


@pytest.mark.asyncio
async def test_start_control_plane_failure(deployment_config: DeploymentConfig) -> None:
    # Create deployment instance
    deployment = Deployment(config=deployment_config, root_path=Path("/tmp"))

    # Mock control plane methods
    deployment._control_plane.register_to_message_queue = mock.AsyncMock(  # type: ignore
        return_value=mock.AsyncMock()
    )
    deployment._control_plane.launch_server = mock.AsyncMock()  # type: ignore

    # Create a mock attempt
    mock_attempt: asyncio.Future = asyncio.Future()
    mock_attempt.set_exception(Exception("Connection failed"))

    # Mock AsyncRetrying to raise an exception
    with mock.patch(
        "llama_deploy.apiserver.deployment.AsyncRetrying",
        side_effect=RetryError(last_attempt=mock_attempt),  # type: ignore
    ):
        # Verify DeploymentError is raised
        with pytest.raises(DeploymentError) as exc_info:
            await deployment._start_control_plane()

        assert "Unable to reach Control Plane" in str(exc_info.value)

        # Verify control plane methods were still called
        deployment._control_plane.register_to_message_queue.assert_called_once()
        deployment._control_plane.launch_server.assert_called_once()


@pytest.mark.asyncio
async def test_start_sequence(deployment_config: DeploymentConfig) -> None:
    deployment = Deployment(config=deployment_config, root_path=Path("/tmp"))
    deployment._start_control_plane = mock.AsyncMock()  # type: ignore
    deployment._run_services = mock.AsyncMock()  # type: ignore
    await deployment.start()
    deployment._start_control_plane.assert_awaited_once()
    # no services should start
    deployment._run_services.assert_not_awaited()
