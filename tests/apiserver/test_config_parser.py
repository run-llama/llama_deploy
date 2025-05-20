from pathlib import Path

from llama_deploy.apiserver.deployment_config_parser import DeploymentConfig


def do_assert(config: DeploymentConfig) -> None:
    assert config.name == "MyDeployment"

    assert config.control_plane.port == 8000

    assert config.message_queue is not None
    assert config.message_queue.type == "simple"
    assert config.default_service == "myworkflow"

    wf_config = config.services["myworkflow"]
    assert wf_config.name == "My Python Workflow"
    assert wf_config.source
    assert wf_config.source.type == "git"
    assert wf_config.source.name == "git@github.com/myorg/myrepo"
    assert wf_config.path == "src/python/app"
    assert wf_config.port == 1313
    assert wf_config.python_dependencies
    assert len(wf_config.python_dependencies) == 3
    assert wf_config.env == {"VAR_1": "x", "VAR_2": "y"}
    assert wf_config.env_files == ["./.env"]

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


def test_load_config_file(data_path: Path) -> None:
    config = DeploymentConfig.from_yaml(data_path / "example.yaml")
    do_assert(config)


def test_from_yaml_bytes(data_path: Path) -> None:
    with open(data_path / "example.yaml", "rb") as config_f:
        config = DeploymentConfig.from_yaml_bytes(config_f.read())
        do_assert(config)
