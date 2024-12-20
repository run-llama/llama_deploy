import asyncio
from typing import Any

import pytest_asyncio

from llama_deploy.message_queues.simple.server import SimpleMessageQueueServer


@pytest_asyncio.fixture(scope="function")
async def message_queue_server() -> Any:
    """Starts a SimpleMessageQueueServer instance ready to serve requests."""
    mqs = SimpleMessageQueueServer()
    server_task = asyncio.create_task(mqs.launch_server())
    await asyncio.sleep(0.5)
    yield
    server_task.cancel()
    await server_task
