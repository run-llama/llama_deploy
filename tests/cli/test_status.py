from unittest import mock

from click.testing import CliRunner

from llama_deploy.cli import llamactl
from llama_deploy.types.apiserver import Status, StatusEnum


def test_status_raised(runner: CliRunner) -> None:
    with mock.patch("llama_deploy.cli.status.Client") as mocked_client:
        mocked_client.return_value.sync.apiserver.status.side_effect = Exception()
        result = runner.invoke(llamactl, ["-s", "https://test", "status"])
        assert result.exit_code == 1


def test_status_server_down(runner: CliRunner) -> None:
    with mock.patch("llama_deploy.cli.status.Client") as mocked_client:
        mocked_client.return_value.sync.apiserver.status.return_value = Status(
            status=StatusEnum.DOWN, status_message="API Server is down for tests"
        )
        result = runner.invoke(llamactl, ["-s", "https://test", "status"])
        assert result.exit_code == 0
        assert "LlamaDeploy is unhealthy: API Server is down for tests" in result.output


def test_status_unhealthy(runner: CliRunner) -> None:
    with mock.patch("llama_deploy.cli.status.Client") as mocked_client:
        mocked_client.return_value.sync.apiserver.status.return_value = Status(
            status=StatusEnum.UNHEALTHY, status_message="test_message"
        )

        result = runner.invoke(llamactl, ["status"])
        assert result.exit_code == 0
        assert "LlamaDeploy is unhealthy: test_message" in result.output


def test_status(runner: CliRunner) -> None:
    with mock.patch("llama_deploy.cli.status.Client") as mocked_client:
        mocked_client.return_value.sync.apiserver.status.return_value = Status(
            status=StatusEnum.HEALTHY, status_message="test_message"
        )
        result = runner.invoke(llamactl, ["status"])
        assert result.exit_code == 0
        assert (
            result.output
            == "LlamaDeploy is up and running.\n\nCurrently there are no active deployments\n"
        )


def test_status_with_deployments(runner: CliRunner) -> None:
    with mock.patch("llama_deploy.cli.status.Client") as mocked_client:
        mocked_client.return_value.sync.apiserver.status.return_value = Status(
            status=StatusEnum.HEALTHY,
            status_message="test_message",
            deployments=["foo", "bar"],
        )

        result = runner.invoke(llamactl, ["status"])

        assert result.exit_code == 0
        assert result.output == (
            "LlamaDeploy is up and running.\n\nActive deployments:\n- foo\n- bar\n"
        )
