import pytest

from llama_deploy import Client
from llama_deploy.types.core import ServiceDefinition


@pytest.mark.e2e
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


@pytest.mark.e2e
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
