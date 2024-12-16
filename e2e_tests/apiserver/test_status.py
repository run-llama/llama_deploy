import pytest


@pytest.mark.asyncio
async def test_status_down(client):
    res = await client.apiserver.status()
    assert res.status.value == "Down"


def test_status_down_sync(client):
    res = client.sync.apiserver.status()
    assert res.status.value == "Down"


@pytest.mark.asyncio
async def test_status_up(apiserver, client):
    res = await client.apiserver.status()
    assert res.status.value == "Healthy"


def test_status_up_sync(apiserver, client):
    res = client.sync.apiserver.status()
    assert res.status.value == "Healthy"
