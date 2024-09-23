import asyncio
from copy import deepcopy
from pathlib import Path
from unittest import mock

import pytest

from llama_deploy.apiserver.config_parser import Config
from llama_deploy.apiserver.deployment import Deployment, Manager
from llama_deploy.message_queues import SimpleMessageQueue
from llama_deploy.control_plane import ControlPlaneServer


def test_deployment_ctor(data_path: Path) -> None:
    config = Config.from_yaml(data_path / "git_service.yaml")
    with mock.patch("llama_deploy.apiserver.deployment.SOURCE_MANAGERS") as sm_dict:
        sm_dict["git"] = mock.MagicMock()
        d = Deployment(config=config, root_path=Path("."))

        sm_dict["git"].sync.assert_called_once()
        assert d.name == "TestDeployment"
        assert d.path.name == "TestDeployment"
        assert type(d._queue) is SimpleMessageQueue
        assert type(d._control_plane) is ControlPlaneServer
        assert len(d._workflow_services) == 1


def test_deployment_ctor_malformed_config(data_path: Path) -> None:
    config = Config.from_yaml(data_path / "git_service.yaml")
    config.services["test-workflow"].path = None
    with pytest.raises(
        ValueError, match="path field in service definition must be set"
    ):
        Deployment(config=config, root_path=Path("."))


def test_deployment_ctor_skip_default_service(data_path: Path) -> None:
    config = Config.from_yaml(data_path / "git_service.yaml")
    config.services["test-workflow2"] = deepcopy(config.services["test-workflow"])
    config.services["test-workflow2"].source = None

    with mock.patch("llama_deploy.apiserver.deployment.SOURCE_MANAGERS") as sm_dict:
        sm_dict["git"] = mock.MagicMock()
        d = Deployment(config=config, root_path=Path("."))
        assert len(d._workflow_services) == 1


def test_manager_ctor() -> None:
    m = Manager()
    assert str(m._deployments_path) == ".deployments"
    assert len(m._deployments) == 0
    m = Manager(deployments_path=Path("foo"))
    assert str(m._deployments_path) == "foo"
    assert len(m._deployments) == 0


def test_manager_deploy_duplicate(data_path: Path) -> None:
    config = Config.from_yaml(data_path / "git_service.yaml")

    m = Manager()
    m._deployments["TestDeployment"] = mock.MagicMock()

    with pytest.raises(ValueError, match="Deployment already exists: TestDeployment"):
        m.deploy(config)


def test_manager_deploy_maximum_reached(data_path: Path) -> None:
    config = Config.from_yaml(data_path / "git_service.yaml")

    m = Manager(max_deployments=1)
    m._deployments["AnotherDeployment"] = mock.MagicMock()

    with pytest.raises(
        ValueError,
        match="Reached the maximum number of deployments, cannot schedule more",
    ):
        m.deploy(config)


def test_manager_deploy(data_path: Path) -> None:
    config = Config.from_yaml(data_path / "git_service.yaml")
    with mock.patch(
        "llama_deploy.apiserver.deployment.Deployment"
    ) as mocked_deployment:
        m = Manager()
        m.deploy(config)
        mocked_deployment.assert_called_once()


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
