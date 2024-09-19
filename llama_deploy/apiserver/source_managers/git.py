from typing import Any

from git import Repo


class GitSourceManager:
    def sync(self, source: str, destination: str | None = None) -> None:
        if not destination:
            raise ValueError("Destination cannot be empty")

        kwargs: dict[str, Any] = {}
        toks = source.split("@")
        if len(toks) == 2:
            branch_name = toks[1]
            kwargs["multi_options"] = [f"-b {branch_name}", "--single-branch"]
        kwargs["url"] = toks[0]
        kwargs["to_path"] = destination

        Repo.clone_from(**kwargs)
