import asyncio
from typing import AsyncGenerator

import pytest

from llama_deploy.client import Client
from llama_deploy.client.models import Collection, Model
from llama_deploy.client.models.model import _async_gen_to_list, make_sync


class SomeAsyncModel(Model):
    async def method(self) -> int:
        return 0

    async def generator_method(self) -> AsyncGenerator:
        yield 4
        yield 2


def test_make_sync() -> None:
    assert asyncio.iscoroutinefunction(getattr(SomeAsyncModel, "method"))
    some_sync = make_sync(SomeAsyncModel)
    assert not asyncio.iscoroutinefunction(getattr(some_sync, "method"))


def test_make_sync_instance(client: Client) -> None:
    some_sync = make_sync(SomeAsyncModel)(client=client, id="foo")
    assert not asyncio.iscoroutinefunction(some_sync.method)
    assert some_sync.method() + 1 == 1
    assert some_sync.generator_method() == [4, 2]


def test__prepare(client: Client) -> None:
    some_sync = make_sync(SomeAsyncModel)(client=client, id="foo")
    coll = some_sync._prepare(Collection)
    assert coll._instance_is_sync


def test_collection_get() -> None:
    class MyCollection(Collection):
        pass

    c = Client()
    models_list = [
        SomeAsyncModel(client=c, id="foo"),
        SomeAsyncModel(client=c, id="bar"),
    ]

    coll = MyCollection(client=c, items={m.id: m for m in models_list})
    assert coll.get("foo").id == "foo"
    assert coll.get("bar").id == "bar"


@pytest.mark.asyncio
async def test__async_gen_to_list() -> None:
    async def aiter_lines():  # type: ignore
        yield "one"
        yield "two"

    assert await _async_gen_to_list(aiter_lines()) == ["one", "two"]
