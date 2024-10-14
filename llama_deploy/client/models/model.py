import asyncio
from typing import Any, Generic, TypeVar, cast

from asgiref.sync import async_to_sync
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from typing_extensions import Self

from llama_deploy.client.base import _BaseClient


class _Base(BaseModel):
    client: _BaseClient = Field(exclude=True)
    _instance_is_sync: bool = PrivateAttr(default=False)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __new__(cls, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise TypeError("Please use instance() instead of direct instantiation")

    @classmethod
    def instance(cls, make_sync: bool = False, **kwargs: Any) -> Self:
        if make_sync:
            cls = _make_sync(cls)

        inst = super(_Base, cls).__new__(cls)
        inst.__init__(**kwargs)  # type: ignore[misc]
        inst._instance_is_sync = make_sync
        return inst


T = TypeVar("T", bound=_Base)


class Model(_Base):
    id: str


class Collection(_Base, Generic[T]):
    items: dict[str, T]

    def get(self, id: str) -> T:
        return self.items[id]

    def list(self) -> list[T]:
        return [self.get(id) for id in self.items.keys()]


def _make_sync(_class: type[T]) -> type[T]:
    class Wrapper(_class):  # type: ignore
        pass

    for name, method in _class.__dict__.items():
        if asyncio.iscoroutinefunction(method) and not name.startswith("_"):
            setattr(Wrapper, name, async_to_sync(method))
    return cast(type[T], Wrapper)
