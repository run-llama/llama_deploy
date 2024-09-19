from copy import deepcopy
from pathlib import Path
from unittest import mock

import pytest

from llama_deploy.apiserver.config_parser import Config
from llama_deploy.apiserver.deployment import Deployment
from llama_deploy.message_queues import SimpleMessageQueue
from llama_deploy.control_plane import ControlPlaneServer

# def test_deploy_git(data_path: Path, tmp_path: Path) -> None:
#     print(tmp_path)
#     config = Config.from_yaml(data_path / "git_service.yaml")
#     manager = Manager(tmp_path)
#     manager.deploy(config)


def test_deploy_ctor(data_path: Path) -> None:
    config = Config.from_yaml(data_path / "git_service.yaml")
    with mock.patch("llama_deploy.apiserver.deployment.SOURCE_MANAGERS") as sm_dict:
        sm_dict["git"] = mock.MagicMock()
        d = Deployment(config=config, root_path=Path("."))

        sm_dict["git"].sync.assert_called_once()
        assert d.name == "TestDeployment"
        assert str(d.path) == "TestDeployment"
        assert d.thread is None
        assert type(d._queue) is SimpleMessageQueue
        assert type(d._control_plane) is ControlPlaneServer
        assert len(d._workflow_services) == 1


def test_deploy_ctor_malformed_config(data_path: Path) -> None:
    config = Config.from_yaml(data_path / "git_service.yaml")
    config.services["test-workflow"].path = None
    with pytest.raises(
        ValueError, match="path field in service definition must be set"
    ):
        Deployment(config=config, root_path=Path("."))


def test_deploy_ctor_skip_default_service(data_path: Path) -> None:
    config = Config.from_yaml(data_path / "git_service.yaml")
    config.services["test-workflow2"] = deepcopy(config.services["test-workflow"])
    config.services["test-workflow2"].source = None

    with mock.patch("llama_deploy.apiserver.deployment.SOURCE_MANAGERS") as sm_dict:
        sm_dict["git"] = mock.MagicMock()
        d = Deployment(config=config, root_path=Path("."))
        assert len(d._workflow_services) == 1
