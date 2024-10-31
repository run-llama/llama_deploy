import asyncio
from typing import Any, Generic, TypeVar, cast

from asgiref.sync import async_to_sync
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from typing_extensions import Self

from llama_deploy.client.base import _BaseClient


class _Base(BaseModel):
    """The base model provides fields and functionalities common to derived models and collections."""

    client: _BaseClient = Field(exclude=True)
    _instance_is_sync: bool = PrivateAttr(default=False)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __new__(cls, *args, **kwargs):  # type: ignore[no-untyped-def]
        """We prevent the usage of the constructor and force users to call `instance()` instead."""
        raise TypeError("Please use instance() instead of direct instantiation")

    @classmethod
    def instance(cls, make_sync: bool = False, **kwargs: Any) -> Self:
        """Returns an instance of the given model.

        Using the class constructor is not possible because we want to alter the class method to
        accommodate sync/async usage before creating an instance, and __init__ would be too late.
        """
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
    """A generic container of items of the same model type."""

    items: dict[str, T]

    def get(self, id: str) -> T:
        """Returns an item from the collection."""
        return self.items[id]

    def list(self) -> list[T]:
        """Returns a list of all the items in the collection."""
        return [self.get(id) for id in self.items.keys()]


def _make_sync(_class: type[T]) -> type[T]:
    """Wraps the methods of the given model class so that they can be called without `await`."""

    class Wrapper(_class):  # type: ignore
        pass

    for name, method in _class.__dict__.items():
        # Only wrap async public methods
        if asyncio.iscoroutinefunction(method) and not name.startswith("_"):
            setattr(Wrapper, name, async_to_sync(method))
    # Static type checkers can't assess Wrapper is indeed a type[T], let's promise it is.
    return cast(type[T], Wrapper)
