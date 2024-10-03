from typing import Protocol

from .git import GitSourceManager
from .local import LocalSourceManager

__all__ = ["GitSourceManager", "LocalSourceManager"]


class SourceManager(Protocol):
    """Protocol to be implemented by classes responsible for managing Deployment sources."""

    def sync(
        self, source: str, destination: str | None = None
    ) -> None:  # pragma: no cover
        """Fetches resources from `source` so they can be used in a deployment.

        Optionally uses `destination` to store data when this makes sense for the
        specific source type.
        """
