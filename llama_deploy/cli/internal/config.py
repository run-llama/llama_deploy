from pathlib import Path
from typing import Any

import yaml
from platformdirs import user_config_dir
from pydantic import BaseModel

DEFAULT_PROFILE_NAME = "default"


class ConfigProfile(BaseModel):
    server: str = "http://localhost:4501"
    insecure: bool = False
    timeout: float = 120.0


def _create_default_profile() -> dict[str, dict[str, Any]]:
    return {DEFAULT_PROFILE_NAME: ConfigProfile().model_dump()}


def _default_config_path() -> Path:
    cfg_path = Path(user_config_dir("llamactl", appauthor=False)) / "config.yaml"
    if not cfg_path.exists():
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg_path, "w") as f:
            yaml.safe_dump(_create_default_profile(), f)

    return cfg_path


def load_config(path: Path | None = None) -> dict[str, ConfigProfile]:
    if path is None:
        path = _default_config_path()

    with open(path) as f:
        config = yaml.safe_load(f.read())

    ret = dict()
    for name, dump in config.items():
        ret[name] = ConfigProfile(**dump)

    return ret
