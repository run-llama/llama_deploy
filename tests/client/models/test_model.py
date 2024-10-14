import asyncio

import pytest

from llama_deploy.client import Client
from llama_deploy.client.models import Collection, Model
from llama_deploy.client.models.model import _make_sync


class SomeAsyncModel(Model):
    async def method(self) -> None:
        pass


def test_no_init(client: Client) -> None:
    with pytest.raises(
        TypeError, match=r"Please use instance\(\) instead of direct instantiation"
    ):
        SomeAsyncModel(id="foo", client=client)


def test_make_sync() -> None:
    assert asyncio.iscoroutinefunction(getattr(SomeAsyncModel, "method"))
    some_sync = _make_sync(SomeAsyncModel)
    assert not asyncio.iscoroutinefunction(getattr(some_sync, "method"))


def test_collection_get() -> None:
    class MyCollection(Collection):
        pass

    c = Client()
    models_list = [
        SomeAsyncModel.instance(client=c, id="foo"),
        SomeAsyncModel.instance(client=c, id="bar"),
    ]

    coll = MyCollection.instance(client=c, items={m.id: m for m in models_list})
    assert coll.get("foo").id == "foo"
    assert coll.get("bar").id == "bar"
    assert coll.list() == models_list
