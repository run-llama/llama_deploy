import shutil
from pathlib import Path
from typing import IO, Any, Mapping, Optional, Sequence, Union

import pytest
from click import BaseCommand
from click.testing import CliRunner, Result


class ConfigCliRunner(CliRunner):
    tests_data_path: Path
    temp_config: Path

    def invoke(
        self,
        cli: "BaseCommand",
        args: Optional[Union[str, Sequence[str]]] = None,
        input: Optional[Union[str, bytes, IO[Any]]] = None,
        env: Optional[Mapping[str, Optional[str]]] = None,
        catch_exceptions: bool = True,
        color: bool = False,
        **extra: Any,
    ) -> Result:
        args = args or []
        if "-c" not in args and "--config" not in args:
            # If the config file was not specified explicitly in the test,
            # we set it globally
            args = ["-c", str(self.tests_data_path / "config.yaml")] + list(args)
        else:
            args = ["-c", str(self.temp_config)] + list(args)

        return super().invoke(cli, args, input, env, catch_exceptions, color, **extra)


@pytest.fixture
def data_path() -> Path:
    return Path(__file__).parent / "data"


@pytest.fixture
def runner(data_path: Path, tmp_config: Path) -> CliRunner:
    runner = ConfigCliRunner()
    runner.tests_data_path = data_path
    runner.temp_config = tmp_config
    return runner


@pytest.fixture
def tmp_config(data_path: Path, tmp_path: Path) -> Path:
    src = data_path / "config.yaml"
    dst = tmp_path / "config.yaml"
    shutil.copy(src, tmp_path)
    return dst
