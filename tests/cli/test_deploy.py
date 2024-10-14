from pathlib import Path
from unittest import mock

from click.testing import CliRunner

from llama_deploy.cli import llamactl


def test_deploy(runner: CliRunner, data_path: Path) -> None:
    test_config_file = data_path / "deployment.yaml"
    mocked_response = mock.MagicMock(status_code=200, json=lambda: {})
    with mock.patch("llama_deploy.cli.utils.httpx.request") as mocked_httpx:
        mocked_httpx.return_value = mocked_response
        result = runner.invoke(llamactl, ["-t", "5.0", "deploy", str(test_config_file)])

        assert result.exit_code == 0
        with open(test_config_file, "rb") as f:
            mocked_httpx.assert_called_with(
                "POST",
                "http://localhost:4501/deployments/create",
                files={"config_file": f.read()},
                verify=True,
                timeout=5,
            )


def test_deploy_failed(runner: CliRunner, data_path: Path) -> None:
    test_config_file = data_path / "deployment.yaml"
    mocked_response = mock.MagicMock(
        status_code=401, json=lambda: {"detail": "Unauthorized!"}
    )
    with mock.patch("llama_deploy.cli.utils.httpx.request") as mocked_httpx:
        mocked_httpx.return_value = mocked_response
        result = runner.invoke(llamactl, ["deploy", str(test_config_file)])
        assert result.exit_code == 1
        assert result.output == "Error: Unauthorized!\n"
