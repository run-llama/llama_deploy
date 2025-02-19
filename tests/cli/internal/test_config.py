from pathlib import Path
from unittest import mock

from llama_deploy.cli.internal.config import (
    _default_config_path,
    _dump_default_profile,
    load_config,
)


def test__dump_default_profile() -> None:
    assert _dump_default_profile() == {
        "default": {
            "insecure": False,
            "server": "http://localhost:4501",
            "timeout": 120.0,
        }
    }


def test__default_config_path(tmp_path: Path) -> None:
    with mock.patch(
        "llama_deploy.cli.internal.config.user_config_dir"
    ) as mock_config_dir:
        mock_config_dir.return_value = tmp_path
        _default_config_path()
        config = load_config(tmp_path / "config.yaml")
        assert "default" in config


def test_load_config(data_path: Path) -> None:
    test_config_file = data_path / "config.yaml"
    with mock.patch(
        "llama_deploy.cli.internal.config._default_config_path"
    ) as mock_path:
        mock_path.return_value = test_config_file
        config = load_config(path=None)
        assert "test" in config
