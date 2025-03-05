import asyncio
import multiprocessing

import pytest

from llama_deploy import (
    Client,
)
from llama_deploy.types.core import ServiceDefinition

from .conftest import run_async_workflow


def test_services(workflow):
    client = Client()

    services = client.sync.core.services
    assert len(services.list()) == 1

    services.deregister("basic")
    assert len(services.items) == 0

    new_s = services.register(
        ServiceDefinition(service_name="another_basic", description="none")
    )
    assert new_s.id == "another_basic"
    assert len(services.items) == 1


@pytest.mark.asyncio
async def test_services_async(workflow):
    client = Client()

    assert len(await client.core.services.list()) == 1
    await client.core.services.deregister("basic")
    assert len(await client.core.services.list()) == 0

    new_s = await client.core.services.register(
        ServiceDefinition(service_name="another_basic", description="none")
    )
    assert new_s.id == "another_basic"
    assert len(await client.core.services.list()) == 1


@pytest.mark.asyncio
async def test_service_restart(core):
    client = Client()

    # create workflow service in a separate process
    p = multiprocessing.Process(target=run_async_workflow)
    p.start()
    await asyncio.sleep(5)

    # create session
    session = await client.core.sessions.create()

    # run
    result = await session.run("basic")
    assert result == "n/a_result"

    # kill the service
    p.kill()
    p.join()

    # restart the service
    p = multiprocessing.Process(target=run_async_workflow)
    p.start()
    await asyncio.sleep(5)

    # run again, same session
    result = await session.run("basic")
    assert result == "n/a_result"

    # assert len(await client.core.services.list()) == 1
    # await client.core.services.deregister("basic")
    # assert len(await client.core.services.list()) == 0

    # new_s = await client.core.services.register(
    #     ServiceDefinition(service_name="another_basic", description="none")
    # )
    # assert new_s.id == "another_basic"
    # assert len(await client.core.services.list()) == 1

    p.kill()
    p.join()
