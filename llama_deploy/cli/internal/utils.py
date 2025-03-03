from pathlib import Path

from platformdirs import user_config_dir

DEFAULT_PROFILE_NAME = "default"
DEFAULT_CONFIG_FILE_NAME = "config.yaml"
DEFAULT_CONFIG_FOLDER_NAME = "llamactl"


def _default_config_path() -> Path:
    base = user_config_dir(DEFAULT_CONFIG_FOLDER_NAME, appauthor=False)
    return Path(base) / DEFAULT_CONFIG_FILE_NAME
