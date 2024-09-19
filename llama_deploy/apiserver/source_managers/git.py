from typing import Any

from git import Repo


class GitSourceManager:
    def sync(self, source: str, destination: str | None = None) -> None:
        if not destination:
            raise ValueError("Destination cannot be empty")

        url, branch_name = self._parse_source(source)
        kwargs: dict[str, Any] = {"url": url, "to_path": destination}
        if branch_name:
            kwargs["multi_options"] = [f"-b {branch_name}", "--single-branch"]

        Repo.clone_from(**kwargs)

    @staticmethod
    def _parse_source(source: str) -> tuple[str, str | None]:
        branch_name = None
        toks = source.split("@")
        url = toks[0]
        if len(toks) > 1:
            branch_name = toks[1]

        return url, branch_name
