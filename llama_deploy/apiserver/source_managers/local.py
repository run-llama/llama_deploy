import shutil
from pathlib import Path

from .base import SourceManager, SyncPolicy


class LocalSourceManager(SourceManager):
    """A SourceManager specialized for sources of type `local`."""

    def sync(
        self,
        source: str,
        destination: str | None = None,
        sync_policy: SyncPolicy = SyncPolicy.REPLACE,
    ) -> None:
        """Copies the folder with path `source` into a local path `destination`.

        Args:
            source: The filesystem path to the folder containing the source code.
            destination: The path in the local filesystem where to copy the source directory.
        """
        if not destination:
            raise ValueError("Destination cannot be empty")

        final_path = self._config.base_path / source
        destination_path = Path(destination)
        dirs_exist_ok: bool = False
        try:
            if destination_path.exists():
                # Path is a non-empty directory
                if sync_policy == SyncPolicy.REPLACE:
                    shutil.rmtree(destination)
                elif sync_policy == SyncPolicy.MERGE:
                    dirs_exist_ok = True
                elif sync_policy == SyncPolicy.SKIP:
                    return

            shutil.copytree(final_path, destination, dirs_exist_ok=dirs_exist_ok)
        except Exception as e:
            msg = f"Unable to copy {source} into {destination}: {e}"
            raise ValueError(msg) from e
