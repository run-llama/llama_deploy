from unittest import mock

from click.testing import CliRunner

from llama_deploy.cli import llamactl


def test_run(runner: CliRunner) -> None:
    mocked_response = mock.MagicMock(status_code=200, json=lambda: {})
    with mock.patch("llama_deploy.cli.run.httpx") as mocked_httpx:
        mocked_httpx.post.return_value = mocked_response
        result = runner.invoke(
            llamactl, ["run", "-d", "deployment_name", "-s", "service_name"]
        )
        mocked_httpx.post.assert_called_with(
            "http://localhost:4501/deployments/deployment_name/tasks/create",
            verify=True,
            json={"input": "{}", "agent_id": "service_name"},
            timeout=5.0,
        )
        assert result.exit_code == 0


def test_run_error(runner: CliRunner) -> None:
    mocked_response = mock.MagicMock(
        status_code=500, json=lambda: {"detail": "test error"}
    )
    with mock.patch("llama_deploy.cli.run.httpx") as mocked_httpx:
        mocked_httpx.post.return_value = mocked_response
        result = runner.invoke(llamactl, ["run", "-d", "deployment_name"])
        assert result.exit_code == 1
        assert result.output == "Error: test error\n"


def test_run_args(runner: CliRunner) -> None:
    mocked_response = mock.MagicMock(status_code=200, json=lambda: {})
    with mock.patch("llama_deploy.cli.run.httpx") as mocked_httpx:
        mocked_httpx.post.return_value = mocked_response
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
        mocked_httpx.post.assert_called_with(
            "http://localhost:4501/deployments/deployment_name/tasks/create",
            verify=True,
            json={
                "input": '{"first_arg": "first_value", "second_arg": "\\"second value with spaces\\""}',
            },
            timeout=5.0,
        )
        assert result.exit_code == 0
