from pathlib import Path
from unittest import mock

import pytest

from llama_deploy.apiserver import DeploymentConfig
from llama_deploy.apiserver.source_managers.local import LocalSourceManager


@pytest.fixture
def config(data_path: Path) -> DeploymentConfig:
    return DeploymentConfig.from_yaml(data_path / "local.yaml")


def test_dest_missing(config: DeploymentConfig) -> None:
    sm = LocalSourceManager(config)
    with pytest.raises(ValueError, match="Destination cannot be empty"):
        sm.sync("source", "")


def test_sync_error(config: DeploymentConfig) -> None:
    sm = LocalSourceManager(config)
    with mock.patch(
        "llama_deploy.apiserver.source_managers.local.shutil"
    ) as shutil_mock:
        shutil_mock.copytree.side_effect = Exception("this was a test")
        with pytest.raises(
            ValueError, match="Unable to copy source into dest: this was a test"
        ):
            sm.sync("source", "dest")


def test_relative_path(tmp_path: Path, data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "local.yaml")
    sm = LocalSourceManager(config)

    sm.sync("workflow", str(tmp_path))
    fnames = list(f.name for f in tmp_path.iterdir())
    assert "workflow_test.py" in fnames
    assert "__init__.py" in fnames


def test_relative_path_dot(tmp_path: Path, data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "local.yaml")
    sm = LocalSourceManager(config)

    sm.sync("./workflow", str(tmp_path))
    fnames = list(f.name for f in tmp_path.iterdir())
    assert "workflow_test.py" in fnames
    assert "__init__.py" in fnames


def test_absolute_path(tmp_path: Path, data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "local.yaml")
    wf_dir = data_path / "workflow"
    sm = LocalSourceManager(config)

    sm.sync(str(wf_dir.absolute()), str(tmp_path))
    fnames = list(f.name for f in tmp_path.iterdir())
    assert "workflow_test.py" in fnames
    assert "__init__.py" in fnames
