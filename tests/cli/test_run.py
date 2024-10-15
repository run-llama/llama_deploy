from unittest import mock

from click.testing import CliRunner

from llama_deploy.cli import llamactl


def test_run(runner: CliRunner) -> None:
    mocked_response = mock.MagicMock(status_code=200, json=lambda: {})
    with mock.patch("httpx.post") as mocked_post:
        mocked_post.return_value = mocked_response
        result = runner.invoke(
            llamactl, ["run", "-d", "deployment_name", "-s", "service_name"]
        )
        mocked_post.assert_called_with(
            "http://localhost:4501/deployments/deployment_name/tasks/run",
            verify=True,
            json={"input": "{}", "agent_id": "service_name"},
            timeout=None,
        )
        assert result.exit_code == 0


def test_run_error(runner: CliRunner) -> None:
    mocked_response = mock.MagicMock(
        status_code=500, json=lambda: {"detail": "test error"}
    )
    with mock.patch("httpx.post") as mocked_post:
        mocked_post.return_value = mocked_response
        result = runner.invoke(llamactl, ["run", "-d", "deployment_name"])
        assert result.exit_code == 1
        assert result.output == "Error: test error\n"


def test_run_args(runner: CliRunner) -> None:
    mocked_response = mock.MagicMock(status_code=200, json=lambda: {})
    with mock.patch("httpx.post") as mocked_post:
        mocked_post.return_value = mocked_response
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
        mocked_post.assert_called_with(
            "http://localhost:4501/deployments/deployment_name/tasks/run",
            verify=True,
            json={
                "input": '{"first_arg": "first_value", "second_arg": "\\"second value with spaces\\""}',
            },
            timeout=None,
        )
        assert result.exit_code == 0
