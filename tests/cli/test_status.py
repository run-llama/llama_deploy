from unittest import mock

from click.testing import CliRunner

from llama_deploy.cli import llamactl


def test_status_server_down(runner: CliRunner) -> None:
    result = runner.invoke(llamactl, ["-s", "https://test", "status"])
    assert result.exit_code == 1
    print(result.output)
    assert "Error: Llama Deploy is not responding" in result.output


def test_status_unhealthy(runner: CliRunner) -> None:
    mocked_response = mock.MagicMock(status_code=500)
    with mock.patch("llama_deploy.cli.utils.httpx.request") as mocked_httpx:
        mocked_httpx.return_value = mocked_response
        result = runner.invoke(llamactl, ["status"])
        assert result.exit_code == 0
        assert "Llama Deploy is unhealthy: [500]" in result.output


def test_status(runner: CliRunner) -> None:
    mocked_response = mock.MagicMock(status_code=200, json=lambda: {})
    with mock.patch("llama_deploy.cli.utils.httpx.request") as mocked_httpx:
        mocked_httpx.return_value = mocked_response
        result = runner.invoke(llamactl, ["status"])
        assert result.exit_code == 0
        assert (
            result.output
            == "Llama Deploy is up and running.\n\nCurrently there are no active deployments\n"
        )


def test_status_with_deployments(runner: CliRunner) -> None:
    mocked_response = mock.MagicMock(status_code=200)
    mocked_response.json.return_value = {"deployments": ["foo", "bar"]}
    with mock.patch("llama_deploy.cli.utils.httpx.request") as mocked_httpx:
        mocked_httpx.return_value = mocked_response
        result = runner.invoke(llamactl, ["status"])
        assert result.exit_code == 0
        assert result.output == (
            "Llama Deploy is up and running.\n\nActive deployments:\n- foo\n- bar\n"
        )
