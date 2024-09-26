from unittest import mock

import pytest

from llama_deploy.apiserver.server import lifespan


@pytest.mark.asyncio
@mock.patch("llama_deploy.apiserver.server.manager")
@mock.patch("llama_deploy.apiserver.server.shutil")
async def test_lifespan(mocked_shutil, mocked_manager) -> None:  # type: ignore
    mocked_manager._deployments_path.resolve.return_value = "."
    async with lifespan(mock.MagicMock()):
        pass

    mocked_manager.serve.assert_called_once()
    mocked_shutil.rmtree.assert_called_with(".")
