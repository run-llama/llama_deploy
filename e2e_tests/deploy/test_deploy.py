import asyncio
import logging

import pytest

from llama_deploy import ControlPlaneConfig, SimpleMessageQueueConfig
from llama_deploy.deploy import deploy_core


@pytest.mark.asyncio
async def test_deploy_core(caplog):
    caplog.set_level(logging.INFO)
    t = asyncio.create_task(
        deploy_core(
            control_plane_config=ControlPlaneConfig(),
            message_queue_config=SimpleMessageQueueConfig(),
        )
    )

    await asyncio.sleep(5)
    assert "Launching message queue server at" in caplog.text
    assert "Launching control plane server at" in caplog.text

    for task in asyncio.all_tasks():
        if task is not asyncio.current_task():
            task.cancel()

    try:
        await asyncio.wait_for(t, timeout=5)
    except asyncio.TimeoutError:
        pass


@pytest.mark.asyncio
async def _test_deploy_core_disable_control_plane(caplog):
    caplog.set_level(logging.INFO)
    t = asyncio.create_task(
        deploy_core(
            control_plane_config=ControlPlaneConfig(),
            message_queue_config=SimpleMessageQueueConfig(),
            disable_control_plane=True,
        )
    )

    await asyncio.sleep(5)
    assert "Launching message queue server at" in caplog.text
    assert "Launching control plane server at" not in caplog.text

    t.cancel()
    try:
        await asyncio.wait_for(t, timeout=5)
    except asyncio.TimeoutError:
        pass
