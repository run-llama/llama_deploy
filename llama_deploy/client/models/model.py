import asyncio
from typing import Any, Generic, TypeVar

from asgiref.sync import async_to_sync
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from llama_deploy.client.base import _BaseClient


class _Base(BaseModel):
    """The base model provides fields and functionalities common to derived models and collections."""

    client: _BaseClient = Field(exclude=True)
    _instance_is_sync: bool = PrivateAttr(default=False)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _prepare(self, _class: type) -> type:
        if self._instance_is_sync:
            return make_sync(_class)
        return _class


T = TypeVar("T", bound=_Base)


class Model(_Base):
    id: str


class Collection(_Base, Generic[T]):
    """A generic container of items of the same model type."""

    items: dict[str, T]

    def get(self, id: str) -> T:
        """Returns an item from the collection."""
        return self.items[id]

    def list(self) -> list[T]:
        """Returns a list of all the items in the collection."""
        return [self.get(id) for id in self.items.keys()]


def make_sync(_class: type[T]) -> Any:
    """Wraps the methods of the given model class so that they can be called without `await`."""

    class Wrapper(_class):  # type: ignore
        _instance_is_sync: bool = True

    for name, method in _class.__dict__.items():
        # Only wrap async public methods
        if asyncio.iscoroutinefunction(method) and not name.startswith("_"):
            setattr(Wrapper, name, async_to_sync(method))

    return Wrapper
