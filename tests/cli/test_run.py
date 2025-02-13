from unittest import mock

import httpx
from click.testing import CliRunner

from llama_deploy.cli import llamactl
from llama_deploy.types import TaskDefinition


def test_run(runner: CliRunner) -> None:
    with mock.patch("llama_deploy.cli.run.Client") as mocked_client:
        mocked_deployment = mock.MagicMock()
        mocked_deployment.tasks.run.return_value = mock.MagicMock(id="test_deployment")
        mocked_client.return_value.sync.apiserver.deployments.get.return_value = (
            mocked_deployment
        )

        result = runner.invoke(
            llamactl,
            ["run", "-d", "deployment_name", "-s", "service_name", "-i", "session_id"],
        )

        mocked_client.assert_called_with(
            api_server_url="http://localhost:4501", disable_ssl=False, timeout=120.0
        )

        args = mocked_deployment.tasks.run.call_args
        actual = args[0][0]
        expected = TaskDefinition(service_id="service_name", input="{}")
        assert expected.input == actual.input
        assert expected.service_id == actual.service_id
        assert actual.session_id is not None
        assert result.exit_code == 0


def test_run_error(runner: CliRunner) -> None:
    with mock.patch("llama_deploy.cli.run.Client") as mocked_client:
        mocked_client.return_value.sync.apiserver.deployments.get.side_effect = (
            httpx.HTTPStatusError(
                "test error", response=mock.MagicMock(), request=mock.MagicMock()
            )
        )

        result = runner.invoke(llamactl, ["run", "-d", "deployment_name"])

        assert result.exit_code == 1
        assert result.output == "Error: test error\n"


def test_run_args(runner: CliRunner) -> None:
    with mock.patch("llama_deploy.cli.run.Client") as mocked_client:
        mocked_deployment = mock.MagicMock()
        mocked_deployment.tasks.run.return_value = mock.MagicMock(id="test_deployment")
        mocked_client.return_value.sync.apiserver.deployments.get.return_value = (
            mocked_deployment
        )

        result = runner.invoke(
            llamactl,
            [
                "run",
                "-d",
                "deployment_name",
                "-a",
                "first_arg",
                "first_value",
                "-a",
                "second_arg",
                '"second value with spaces"',
            ],
        )

        args = mocked_deployment.tasks.run.call_args
        actual = args[0][0]
        expected = TaskDefinition(
            input='{"first_arg": "first_value", "second_arg": "\\"second value with spaces\\""}',
        )
        assert expected.input == actual.input
        assert expected.service_id == actual.service_id
        assert actual.session_id is None
        assert result.exit_code == 0
