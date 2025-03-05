from pathlib import Path

import pytest
from click.testing import CliRunner

from llama_deploy.cli import llamactl


def test_get_profiles(runner: CliRunner) -> None:
    result = runner.invoke(llamactl, ["config", "get-profiles"])
    assert result.exit_code == 0
    # Verify default profile is shown
    assert "default" in result.output
    assert "*" in result.output  # Current profile marker


def test_current_profile(runner: CliRunner) -> None:
    result = runner.invoke(llamactl, ["config", "current-profile"])
    assert result.exit_code == 0
    assert "default" in result.output


@pytest.mark.parametrize(
    "profile,expected_code,expected_output",
    [
        ("default", 0, ""),  # Switch to existing profile
        ("nonexistent", 1, "Cannot find profile 'nonexistent'"),  # Invalid profile
    ],
)
def test_use_profile(
    runner: CliRunner,
    profile: str,
    expected_code: int,
    expected_output: str,
    tmp_config: Path,
) -> None:
    result = runner.invoke(
        llamactl, ["-c", str(tmp_config), "config", "use-profile", profile]
    )
    assert result.exit_code == expected_code
    assert expected_output in result.output


@pytest.mark.parametrize(
    "param,value,expected_code,expected_output",
    [
        ("server", "http://localhost:8000", 0, "Set server="),
        ("insecure", "true", 0, "Set insecure="),
        ("insecure", "false", 0, "Set insecure="),
        ("timeout", "30", 0, "Set timeout="),
        ("invalid", "value", 1, "Unknown parameter 'invalid'"),
        ("server", "invalid-url", 1, "Error setting server="),
        ("timeout", "invalid", 1, "Error setting timeout="),
    ],
)
def test_set_profile_vars(
    runner: CliRunner,
    param: str,
    value: str,
    expected_code: int,
    expected_output: str,
    tmp_config: Path,
) -> None:
    result = runner.invoke(
        llamactl, ["-c", str(tmp_config), "config", "set-profile-vars", param, value]
    )
    assert result.exit_code == expected_code
    assert expected_output in result.output


@pytest.mark.parametrize(
    "profile,expected_code,expected_output",
    [
        (
            "default",
            1,
            "Cannot delete profile 'default' because it is currently in use",
        ),
        ("nonexistent", 1, "Cannot find profile 'nonexistent'"),
        ("test", 0, "Profile 'test' has been deleted."),
    ],
)
def test_delete_profile(
    runner: CliRunner,
    profile: str,
    expected_code: int,
    expected_output: str,
    tmp_config: Path,
) -> None:
    result = runner.invoke(
        llamactl, ["-c", str(tmp_config), "config", "delete-profile", profile]
    )
    assert result.exit_code == expected_code
    assert expected_output in result.output


@pytest.mark.parametrize(
    "old_name,new_name,expected_code,expected_output",
    [
        ("default", "new_profile", 0, "has been renamed"),
        ("nonexistent", "new_name", 1, "Cannot find profile 'nonexistent'"),
        (
            "default",
            "default",
            1,
            "Profile 'default' already exists",
        ),
    ],
)
def test_rename_profile(
    runner: CliRunner,
    old_name: str,
    new_name: str,
    expected_code: int,
    expected_output: str,
    tmp_config: Path,
) -> None:
    result = runner.invoke(
        llamactl,
        ["-c", str(tmp_config), "config", "rename-profile", old_name, new_name],
    )
    assert result.exit_code == expected_code
    assert expected_output in result.output

    # If successful, rename back to maintain test isolation
    if expected_code == 0:
        runner.invoke(llamactl, ["config", "rename-profile", new_name, old_name])
