from unittest import mock

import httpx
from click.testing import CliRunner

from llama_deploy.cli import llamactl


def test_session_create(runner: CliRunner) -> None:
    with mock.patch("llama_deploy.cli.sessions.Client") as mocked_client:
        mocked_deployment = mock.MagicMock()
        mocked_deployment.sessions.create.return_value = mock.MagicMock(
            id="test_session"
        )
        mocked_client.return_value.sync.apiserver.deployments.get.return_value = (
            mocked_deployment
        )

        result = runner.invoke(
            llamactl,
            ["sessions", "create", "-d", "deployment_name"],
        )

        mocked_client.assert_called_with(
            api_server_url="http://localhost:4501", disable_ssl=False, timeout=120.0
        )

        mocked_deployment.sessions.create.assert_called_once()
        assert result.exit_code == 0


def test_sessions_create_error(runner: CliRunner) -> None:
    with mock.patch("llama_deploy.cli.sessions.Client") as mocked_client:
        mocked_client.return_value.sync.apiserver.deployments.get.side_effect = (
            httpx.HTTPStatusError(
                "test error", response=mock.MagicMock(), request=mock.MagicMock()
            )
        )

        result = runner.invoke(
            llamactl, ["sessions", "create", "-d", "deployment_name"]
        )

        assert result.exit_code == 1
        assert result.output == "Error: test error\n"
