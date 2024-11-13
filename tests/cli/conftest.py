from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from click.testing import CliRunner


@pytest.fixture
def data_path() -> Path:
    return Path(__file__).parent / "data"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def httpx_request() -> Any:
    with mock.patch("llama_deploy.client.base.httpx") as mocked_httpx:
        yield mocked_httpx.AsyncClient.return_value.__aenter__.return_value.request
