import shutil

from .base import SourceManager


class LocalSourceManager(SourceManager):
    """A SourceManager specialized for sources of type `local`."""

    def sync(self, source: str, destination: str | None = None) -> None:
        """Copies the folder with path `source` into a local path `destination`.

        Args:
            source: The filesystem path to the folder containing the source code.
            destination: The path in the local filesystem where to copy the source directory.
        """
        if not destination:
            raise ValueError("Destination cannot be empty")

        try:
            final_path = self._config.base_path / source
            shutil.copytree(final_path, destination, dirs_exist_ok=True)
        except Exception as e:
            msg = f"Unable to copy {source} into {destination}: {e}"
            raise ValueError(msg) from e
