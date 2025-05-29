import os
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
from click.testing import CliRunner
from tenacity import RetryError

from llama_deploy.apiserver import settings
from llama_deploy.cli.serve import serve


@pytest.fixture
def runner() -> CliRunner:
    """Fixture for invoking command-line interfaces."""
    return CliRunner()


@pytest.fixture(autouse=True)
def ensure_settings_defaults():  # type: ignore
    """Fixture to ensure settings are reset before each test."""
    original_prometheus_enabled = settings.prometheus_enabled
    original_prometheus_port = settings.prometheus_port
    yield
    settings.prometheus_enabled = original_prometheus_enabled
    settings.prometheus_port = original_prometheus_port


def test_serve_no_deployment_file(runner: CliRunner) -> None:
    """Test serve command without a deployment file."""
    with (
        patch("subprocess.Popen") as mock_popen,
        patch("llama_deploy.cli.serve.start_http_server") as mock_start_http_server,
        patch("llama_deploy.cli.serve.Client") as mock_client_class,
    ):
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        settings.prometheus_enabled = False

        mock_sdk_client = MagicMock()
        mock_client_class.return_value = mock_sdk_client

        result = runner.invoke(serve)

        assert result.exit_code == 0
        expected_env = os.environ.copy()
        mock_popen.assert_called_once_with(
            [
                "uvicorn",
                "llama_deploy.apiserver:app",
                "--host",
                "localhost",
                "--port",
                "4501",
            ],
            env=expected_env,
        )
        mock_start_http_server.assert_not_called()
        mock_process.wait.assert_called_once()
        mock_sdk_client.sync.apiserver.deployments.create.assert_not_called()


def test_serve_prometheus_enabled(runner: CliRunner) -> None:
    """Test serve command with Prometheus enabled."""
    with (
        patch("subprocess.Popen") as mock_popen,
        patch("llama_deploy.cli.serve.start_http_server") as mock_start_http_server,
    ):
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        settings.prometheus_enabled = True
        settings.prometheus_port = 9090  # Example port

        result = runner.invoke(serve)

        assert result.exit_code == 0
        mock_start_http_server.assert_called_once_with(9090)
        mock_popen.assert_called_once()  # Args checked in other tests
        mock_process.wait.assert_called_once()


def test_serve_with_deployment_file(runner: CliRunner, tmp_path: Path) -> None:
    """Test serve command with a deployment file."""
    deployment_file = tmp_path / "test_deployment.yaml"
    deployment_file.write_text("dummy content")

    with (
        patch("subprocess.Popen") as mock_popen,
        patch("llama_deploy.cli.serve.start_http_server") as mock_start_http_server,
        patch("llama_deploy.cli.serve.Client") as mock_client_class,
        patch(
            "pathlib.Path.open", mock_open(read_data=b"dummy content")
        ) as mock_file_open,
    ):
        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        mock_sdk_client = MagicMock()
        mock_client_class.return_value = mock_sdk_client
        settings.prometheus_enabled = False

        result = runner.invoke(serve, [str(deployment_file)])

        assert result.exit_code == 0

        expected_env = os.environ.copy()
        expected_env["LLAMA_DEPLOY_APISERVER_DEPLOYMENTS_PATH"] = str(tmp_path)
        mock_popen.assert_called_once_with(
            [
                "uvicorn",
                "llama_deploy.apiserver:app",
                "--host",
                "localhost",
                "--port",
                "4501",
            ],
            env=expected_env,
        )
        mock_start_http_server.assert_not_called()
        mock_client_class.assert_called_once_with()
        mock_file_open.assert_called_once_with("rb")
        mock_sdk_client.sync.apiserver.deployments.create.assert_called_once()
        # Check the first argument of the create call (the file object)
        assert (
            mock_sdk_client.sync.apiserver.deployments.create.call_args[0][0]
            == mock_file_open.return_value
        )
        # Check the local keyword argument
        assert (
            mock_sdk_client.sync.apiserver.deployments.create.call_args[1]["local"]
            is True
        )

        mock_process.wait.assert_called_once()


def test_serve_deployment_creation_fails(runner: CliRunner, tmp_path: Path) -> None:
    """Test serve command when deployment creation fails."""
    deployment_file = tmp_path / "test_deployment_fail.yaml"
    deployment_file.write_text("dummy fail content")

    with (
        patch("subprocess.Popen") as mock_popen,
        patch("llama_deploy.cli.serve.start_http_server"),
        patch("llama_deploy.cli.serve.Client") as mock_client_class,
        patch("pathlib.Path.open", mock_open(read_data=b"dummy content")),
        patch("llama_deploy.cli.serve.RETRY_WAIT_SECONDS", 0.01),
    ):
        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        mock_sdk_client = MagicMock()
        mock_sdk_client.sync.apiserver.deployments.create.side_effect = RetryError(
            "Failed to deploy"  # type: ignore
        )
        mock_client_class.return_value = mock_sdk_client
        settings.prometheus_enabled = False

        result = runner.invoke(serve, [str(deployment_file)])

        assert result.exit_code == 1
        assert "Failed to create deployment" in result.output
        mock_client_class.assert_called_once_with()
        mock_sdk_client.sync.apiserver.deployments.create.assert_called()  # Called 5 times due to retry
        assert mock_sdk_client.sync.apiserver.deployments.create.call_count == 5
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_not_called()


def test_serve_keyboard_interrupt(runner: CliRunner) -> None:
    """Test serve command handles KeyboardInterrupt."""
    with (
        patch("subprocess.Popen") as mock_popen,
        patch("llama_deploy.cli.serve.start_http_server"),
    ):
        mock_process = MagicMock()
        mock_process.wait.side_effect = KeyboardInterrupt
        mock_popen.return_value = mock_process
        settings.prometheus_enabled = False

        result = runner.invoke(serve)

        # Exit code might be 0 or other codes depending on how Click handles KeyboardInterrupt
        # Checking for the message is more reliable here.
        assert "Shutting down..." in result.output
        mock_process.wait.assert_called_once()
