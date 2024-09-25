from pathlib import Path

import pytest
from click.testing import CliRunner


@pytest.fixture
def data_path() -> Path:
    return Path(__file__).parent / "data"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
