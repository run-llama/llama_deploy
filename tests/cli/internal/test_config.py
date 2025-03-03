from pathlib import Path
from unittest import mock

from llama_deploy.cli.internal.config import (
    Config,
    ConfigProfile,
    _default_config_path,
    load_config,
)
from llama_deploy.cli.internal.utils import DEFAULT_CONFIG_FILE_NAME


def test_load_config(data_path: Path) -> None:
    test_config_file = data_path / DEFAULT_CONFIG_FILE_NAME
    config = load_config(path=test_config_file)
    assert "test" in config.profiles


def test_load_config_no_path(tmp_path: Path) -> None:
    test_config_file = tmp_path / DEFAULT_CONFIG_FILE_NAME
    with mock.patch(
        "llama_deploy.cli.internal.utils._default_config_path"
    ) as mock_path:
        mock_path.return_value = test_config_file
        config = load_config(path=None)
        assert len(config.profiles) == 1
        assert "default" in config.profiles


def test__default_config_path() -> None:
    assert str(_default_config_path()).endswith(DEFAULT_CONFIG_FILE_NAME)


def test_config_write(tmp_path: Path) -> None:
    config_path = tmp_path / "test.yaml"
    assert not config_path.exists()
    config = Config(
        current_profile="test", profiles={"test": ConfigProfile()}, path=config_path
    )
    config.write()
    assert config_path.exists()
