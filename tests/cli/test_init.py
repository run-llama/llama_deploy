
import os
import pytest
import tempfile

from click.testing import CliRunner
from llama_deploy.cli import llamactl

@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()

def test_basic_init_e2e(runner: CliRunner):
    with tempfile.TemporaryDirectory() as temp_dir:
        result = runner.invoke(
            llamactl,
            [
                "init",
                "--name", "test-project",
                "--destination", temp_dir,
                "--port", "8080",
                "--message-queue-type", "redis",
                "--template", "basic",
            ],
            input="y\n"  # Confirm UI inclusion
        )
        assert result.exit_code == 0
        assert "Project test-project created successfully!" in result.output

        with open(os.path.join(temp_dir, "test-project", "deployment.yml"), "r") as f:
            text = f.read()
            assert "OPENAI_API_KEY" in text
            assert "ui:" in text
            assert "type: redis" in text

def test_basic_init_e2e_no_ui(runner: CliRunner):
    with tempfile.TemporaryDirectory() as temp_dir:
        result = runner.invoke(
            llamactl,
            [
                "init",
                "--name", "test-project",
                "--destination", temp_dir,
                "--port", "8080",
                "--message-queue-type", "redis",
                "--template", "none",
            ],
        )
        assert result.exit_code == 0
        assert "Project test-project created successfully!" in result.output

        with open(os.path.join(temp_dir, "test-project", "deployment.yml"), "r") as f:
            text = f.read()
            assert "ui: null" in text
