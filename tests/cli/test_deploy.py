from pathlib import Path
from unittest import mock

import httpx
from click.testing import CliRunner

from llama_deploy.cli import llamactl


def test_deploy(runner: CliRunner, data_path: Path) -> None:
    test_config_file = data_path / "deployment.yaml"
    mocked_result = mock.MagicMock(id="test_deployment")
    with mock.patch("llama_deploy.cli.deploy.Client") as mocked_client:
        mocked_client.return_value.sync.apiserver.deployments.create.return_value = (
            mocked_result
        )

        result = runner.invoke(llamactl, ["-t", "5.0", "deploy", str(test_config_file)])

        assert result.exit_code == 0
        assert result.output == "Deployment successful: test_deployment\n"
        mocked_client.assert_called_with(
            api_server_url="http://localhost:4501", disable_ssl=False, timeout=5.0
        )
        file_arg = (
            mocked_client.return_value.sync.apiserver.deployments.create.call_args
        )
        assert str(test_config_file) == file_arg.args[0].name


def test_deploy_failed(runner: CliRunner, data_path: Path) -> None:
    test_config_file = data_path / "deployment.yaml"
    with mock.patch("llama_deploy.cli.deploy.Client") as mocked_client:
        mocked_client.return_value.sync.apiserver.deployments.create.side_effect = (
            httpx.HTTPStatusError(
                "Unauthorized!", response=mock.MagicMock(), request=mock.MagicMock()
            )
        )

        result = runner.invoke(llamactl, ["deploy", str(test_config_file)])
        assert result.exit_code == 1
        assert result.output == "Error: Unauthorized!\n"
