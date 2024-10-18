import asyncio
from typing import TYPE_CHECKING, Generic, TypeVar

from asgiref.sync import async_to_sync
from pydantic import BaseModel

if TYPE_CHECKING:
    from llama_deploy.client import Client


class Model(BaseModel):
    client: Client
    id: str

    class Config:
        exclude = {"client"}
        exclude_none = True


T = TypeVar("T", bound=Model)


class Collection(BaseModel, Generic[T]):
    client: Client
    items: dict[str, T]

    def get(self, id: str) -> T:
        return self.items[id]

    def list(self) -> list[T]:
        return [self.get(id) for id in self.items.keys()]


def make_sync(_class: type[Model]) -> type[Model]:
    class Wrapper(_class):  # type: ignore
        pass

    for name, method in _class.__dict__.items():
        if asyncio.iscoroutinefunction(method) and not name.startswith("_"):
            setattr(Wrapper, name, async_to_sync(method))
    return Wrapper
