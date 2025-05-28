from pathlib import Path
from unittest import mock

import pytest

from llama_deploy.apiserver.deployment_config_parser import DeploymentConfig
from llama_deploy.apiserver.source_managers.git import GitSourceManager


@pytest.fixture
def config(data_path: Path) -> DeploymentConfig:
    return DeploymentConfig.from_yaml(data_path / "git_service.yaml")


def test_parse_source(config: DeploymentConfig) -> None:
    sm = GitSourceManager(config)
    assert sm._parse_source("https://example.com/llama_deploy.git@branch_name") == (
        "https://example.com/llama_deploy.git",
        "branch_name",
    )
    assert sm._parse_source("https://example.com/llama_deploy.git") == (
        "https://example.com/llama_deploy.git",
        None,
    )


def test_sync_wrong_params(config: DeploymentConfig) -> None:
    sm = GitSourceManager(config)
    with pytest.raises(ValueError, match="Destination cannot be empty"):
        sm.sync("some_source")


def test_sync(config: DeploymentConfig) -> None:
    sm = GitSourceManager(config)
    with mock.patch("llama_deploy.apiserver.source_managers.git.Repo") as repo_mock:
        sm.sync("source", "dest")
        repo_mock.clone_from.assert_called_with(to_path="dest", url="source")
        sm.sync("source@branch", "dest")
        repo_mock.clone_from.assert_called_with(
            to_path="dest", url="source", multi_options=["-b branch", "--single-branch"]
        )


def test_sync_dir_exists(config: DeploymentConfig, tmp_path: Path) -> None:
    sm = GitSourceManager(config)
    with mock.patch("llama_deploy.apiserver.source_managers.git.Repo"):
        with mock.patch(
            "llama_deploy.apiserver.source_managers.git.shutil"
        ) as shutil_mock:
            sm.sync("source", str(tmp_path))
            shutil_mock.rmtree.assert_called_once()
