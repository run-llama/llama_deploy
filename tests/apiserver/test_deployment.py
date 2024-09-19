from pathlib import Path

from llama_deploy.apiserver.config_parser import Config
from llama_deploy.apiserver.deployment import Manager


def test_deploy_git(data_path: Path, tmp_path: Path) -> None:
    config = Config.from_yaml(data_path / "git_service.yaml")
    manager = Manager(tmp_path)
    manager.deploy(config)
    print(tmp_path)
