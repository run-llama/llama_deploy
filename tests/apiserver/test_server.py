import logging
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from llama_deploy.apiserver.server import lifespan
from llama_deploy.apiserver.settings import ApiserverSettings


@pytest.mark.asyncio
@mock.patch("llama_deploy.apiserver.server.manager")
@mock.patch("llama_deploy.apiserver.server.shutil")
async def test_lifespan(
    mocked_shutil: Any,
    mocked_manager: Any,
    tmp_path: Path,
    caplog: Any,
    data_path: Path,
) -> None:  # type: ignore
    source_file = data_path / "git_service.yaml"
    config_file = tmp_path / "test.yml"
    with open(config_file, "w") as f:
        f.write(source_file.read_text())

    with mock.patch("llama_deploy.apiserver.server.settings", actual_settings):
        mocked_manager._deployments_path.resolve.return_value = "."
        caplog.set_level(logging.INFO)
        async with lifespan(mock.MagicMock()):
            pass

        assert (
            f"Browsing the rc folder {tmp_path} for deployments to start" in caplog.text
        )
        assert f"Deploying startup configuration from {config_file}" in caplog.text
        mocked_manager.serve.assert_called_once()
        mocked_shutil.rmtree.assert_called_with(".")
