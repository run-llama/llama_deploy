from typing import Protocol

from .git import GitSourceManager

__all__ = ["GitSourceManager"]


class SourceManager(Protocol):
    def sync(self, source: str, destination: str | None = None) -> None:
        ...
