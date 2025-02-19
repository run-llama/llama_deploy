from unittest import mock

from click.testing import CliRunner

from llama_deploy.cli import llamactl
from llama_deploy.cli.__main__ import main


@mock.patch("llama_deploy.cli.__main__.sys")
@mock.patch("llama_deploy.cli.__main__.llamactl")
def test_main(mocked_cli, mocked_sys) -> None:  # type: ignore
    mocked_cli.return_value = 0
    main()
    mocked_sys.exit.assert_called_with(0)


def test_root_command(runner: CliRunner) -> None:
    result = runner.invoke(llamactl)
    assert result.exit_code == 0
    # Ensure invoking the root command outputs the help
    assert "Usage: llamactl" in result.output


def test_wrong_profile(runner: CliRunner) -> None:
    result = runner.invoke(llamactl, ["-p", "foo"])
    assert result.exit_code == 1
