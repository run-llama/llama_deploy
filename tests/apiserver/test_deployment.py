from copy import deepcopy
from pathlib import Path
from unittest import mock

import pytest

from llama_deploy.apiserver.config_parser import (
    Config,
)
from llama_deploy.apiserver.deployment import Deployment, Manager
from llama_deploy.control_plane import ControlPlaneServer
from llama_deploy.message_queues import (
    SimpleRemoteClientMessageQueue,
)


def test_deployment_ctor(data_path: Path) -> None:
    config = Config.from_yaml(data_path / "git_service.yaml")
    with mock.patch("llama_deploy.apiserver.deployment.SOURCE_MANAGERS") as sm_dict:
        sm_dict["git"] = mock.MagicMock()
        d = Deployment(config=config, root_path=Path("."))

        sm_dict["git"].sync.assert_called_once()
        assert d.name == "TestDeployment"
        assert d.path.name == "TestDeployment"
        assert d.thread is None
        assert d._simple_message_queue_task is not None
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


@pytest.mark.asyncio()
async def test_deployment_start(mocked_deployment: Deployment) -> None:
    mocked_deployment._start = mock.AsyncMock()  # type: ignore
    mocked_deployment.start()
    mocked_deployment._start.assert_called_once()


def test_deployment___load_message_queue_default(mocked_deployment: Deployment) -> None:
    q = mocked_deployment._load_message_queue(None)
    assert type(q) is SimpleRemoteClientMessageQueue
    assert q.port == 8001
    assert q.host == "127.0.0.1"


def test_deployment___load_message_queue_not_supported(
    mocked_deployment: Deployment,
) -> None:
    mocked_config = mock.MagicMock(queue_type="does_not_exist")
    with pytest.raises(ValueError, match="Unsupported message queue:"):
        mocked_deployment._load_message_queue(mocked_config)


def test_deployment__load_message_queues(mocked_deployment: Deployment) -> None:
    with mock.patch("llama_deploy.apiserver.deployment.AWSMessageQueue") as m:
        mocked_config = mock.MagicMock(queue_type="aws")
        mocked_config.model_dump.return_value = {"foo": "aws"}
        mocked_deployment._load_message_queue(mocked_config)
        m.assert_called_with(**{"foo": "aws"})

    with mock.patch("llama_deploy.apiserver.deployment.KafkaMessageQueue") as m:
        mocked_config = mock.MagicMock(queue_type="kafka")
        mocked_config.model_dump.return_value = {"foo": "kafka"}
        mocked_deployment._load_message_queue(mocked_config)
        m.assert_called_with(**{"foo": "kafka"})

    with mock.patch("llama_deploy.apiserver.deployment.RabbitMQMessageQueue") as m:
        mocked_config = mock.MagicMock(queue_type="rabbitmq")
        mocked_config.model_dump.return_value = {"foo": "rabbitmq"}
        mocked_deployment._load_message_queue(mocked_config)
        m.assert_called_with(**{"foo": "rabbitmq"})

    with mock.patch("llama_deploy.apiserver.deployment.RedisMessageQueue") as m:
        mocked_config = mock.MagicMock(queue_type="redis")
        mocked_config.model_dump.return_value = {"foo": "redis"}
        mocked_deployment._load_message_queue(mocked_config)
        m.assert_called_with(**{"foo": "redis"})


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


def test_manager_deploy(data_path: Path) -> None:
    config = Config.from_yaml(data_path / "git_service.yaml")
    with mock.patch(
        "llama_deploy.apiserver.deployment.Deployment"
    ) as mocked_deployment:
        m = Manager()
        m.deploy(config)
        mocked_deployment.assert_called_once()
