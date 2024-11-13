from pathlib import Path
from typing import Any
from unittest import mock

import httpx
from click.testing import CliRunner

from llama_deploy.cli import llamactl


def test_deploy(runner: CliRunner, data_path: Path, httpx_request: Any) -> None:
    test_config_file = data_path / "deployment.yaml"
    mocked_response = mock.MagicMock(
        status_code=200, json=lambda: {"name": "test_deployment"}
    )

    httpx_request.return_value = mocked_response
    result = runner.invoke(llamactl, ["-t", "5.0", "deploy", str(test_config_file)])

    print(result.output)
    assert result.exit_code == 0
    with open(test_config_file, "rb") as f:
        httpx_request.assert_called_with(
            "POST",
            "http://localhost:4501/deployments/create",
            files={"config_file": f.read()},
            timeout=5.0,
        )


def test_deploy_failed(runner: CliRunner, data_path: Path, httpx_request: Any) -> None:
    test_config_file = data_path / "deployment.yaml"
    mocked_response = mock.MagicMock(
        status_code=401, json=lambda: {"detail": "Unauthorized!"}
    )
    httpx_request.side_effect = httpx.HTTPStatusError(
        "Unauthorized!", response=mocked_response, request=httpx.Request("", "")
    )

    result = runner.invoke(llamactl, ["deploy", str(test_config_file)])
    assert result.exit_code == 1
    assert result.output == "Error: Unauthorized!\n"
