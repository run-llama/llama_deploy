from pathlib import Path

import pytest

from llama_deploy.apiserver.config_parser import Config


@pytest.fixture
def data_path() -> Path:
    return Path(__file__).parent / "data"


def test_load_config_file(data_path: Path) -> None:
    config = Config.from_yaml(data_path / "example.yaml")
    assert config.name == "MyDeployment"

    assert config.control_plane.port == 8000

    wf_config = config.services["myworkflow"]
    assert wf_config.name == "My Python Workflow"
    assert wf_config.source
    assert wf_config.source.type == "git"
    assert wf_config.source.name == "git@github.com/myorg/myrepo"
    assert wf_config.path == "src/python/app"
    assert wf_config.port == 1313
    assert wf_config.python_dependencies
    assert len(wf_config.python_dependencies) == 3

    wf_config = config.services["another-workflow"]
    assert wf_config.name == "My LITS Workflow"
    assert wf_config.source
    assert wf_config.source.type == "git"
    assert wf_config.source.name == "git@github.com/myorg/myrepo"
    assert wf_config.path == "src/ts/app"
    assert wf_config.port == 1313
    assert wf_config.ts_dependencies
    assert len(wf_config.ts_dependencies) == 2
    assert wf_config.ts_dependencies["@llamaindex/core"] == "^0.2.0"

    wf_config = config.services["dockerservice"]
    assert wf_config.name == "My additional service"
    assert wf_config.source
    assert wf_config.source.type == "docker"
    assert wf_config.source.name == "myorg/myimage:latest"
    assert wf_config.port == 1313

    wf_config = config.services["memory"]
    assert wf_config.name == "Chat Memory"
