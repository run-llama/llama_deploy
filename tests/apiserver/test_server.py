import logging
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from llama_deploy.apiserver.server import lifespan


@pytest.mark.asyncio
@mock.patch("llama_deploy.apiserver.server.manager")
async def test_lifespan(
    mocked_manager: Any,
    tmp_path: Path,
    caplog: Any,
    data_path: Path,
) -> None:  # type: ignore
    source_file = data_path / "git_service.yaml"
    config_file = tmp_path / "test.yml"
    with open(config_file, "w") as f:
        f.write(source_file.read_text())

    mocked_manager.serve = mock.AsyncMock()
    with mock.patch("llama_deploy.apiserver.server.settings") as mocked_settings:
        mocked_settings.rc_path = tmp_path
        mocked_settings.deployments_path = tmp_path / "foo/bar"
        mocked_manager.deployments_path = mocked_settings.deployments_path
        caplog.set_level(logging.INFO)
        async with lifespan(mock.AsyncMock()):
            pass

        assert f"deployments folder: {mocked_settings.deployments_path}" in caplog.text
        assert (
            f"Browsing the rc folder {tmp_path} for deployments to start" in caplog.text
        )
        assert f"Deploying startup configuration from {config_file}" in caplog.text
        mocked_manager.serve.assert_called_once()
