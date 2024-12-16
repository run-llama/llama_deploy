import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_status_down(client):
    res = await client.apiserver.status()
    assert res.status.value == "Down"


@pytest.mark.e2e
def test_status_down_sync(client):
    res = client.sync.apiserver.status()
    assert res.status.value == "Down"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_status_up(apiserver, client):
    res = await client.apiserver.status()
    assert res.status.value == "Healthy"


@pytest.mark.e2e
def test_status_up_sync(apiserver, client):
    res = client.sync.apiserver.status()
    assert res.status.value == "Healthy"
