from pathlib import Path
from typing import IO, Any, Mapping, Optional, Sequence, Union

import pytest
from click import BaseCommand
from click.testing import CliRunner, Result


class ConfigCliRunner(CliRunner):
    config_path: Path

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
        if args and ("-c" not in args and "--config" not in args):
            # If the config file was not specified explicitly in the test,
            # we set it globally
            args = ["-c", str(self.config_path / "config.yaml")] + list(args)

        return super().invoke(cli, args, input, env, catch_exceptions, color, **extra)


@pytest.fixture
def data_path() -> Path:
    return Path(__file__).parent / "data"


@pytest.fixture
def runner(data_path: Path) -> CliRunner:
    runner = ConfigCliRunner()
    runner.config_path = data_path
    return runner
