import os
import tempfile

import pytest
from click.testing import CliRunner

from llama_deploy.cli import llamactl


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_basic_init_e2e(runner: CliRunner) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        result = runner.invoke(
            llamactl,
            [
                "init",
                "--name",
                "test-project",
                "--destination",
                temp_dir,
                "--template",
                "basic",
            ],
            input="y\n",  # Confirm UI inclusion
        )
        assert result.exit_code == 0
        assert "Project test-project created successfully!" in result.output

        with open(os.path.join(temp_dir, "test-project", "deployment.yml"), "r") as f:
            text = f.read()
            assert "OPENAI_API_KEY" in text
            assert "ui:" in text


def test_basic_init_e2e_no_ui(runner: CliRunner) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        result = runner.invoke(
            llamactl,
            [
                "init",
                "--name",
                "test-project",
                "--destination",
                temp_dir,
                "--template",
                "none",
            ],
        )
        assert result.exit_code == 0
        assert "Project test-project created successfully!" in result.output

        with open(os.path.join(temp_dir, "test-project", "deployment.yml"), "r") as f:
            text = f.read()
            assert "ui: null" in text
