from unittest import mock

import pytest

from llama_deploy.apiserver.source_managers.git import GitSourceManager


def test_parse_source() -> None:
    sm = GitSourceManager()
    assert sm._parse_source("https://example.com/llama_deploy.git@branch_name") == (
        "https://example.com/llama_deploy.git",
        "branch_name",
    )
    assert sm._parse_source("https://example.com/llama_deploy.git") == (
        "https://example.com/llama_deploy.git",
        None,
    )


def test_sync_wrong_params() -> None:
    sm = GitSourceManager()
    with pytest.raises(ValueError, match="Destination cannot be empty"):
        sm.sync("some_source")


def test_sync() -> None:
    sm = GitSourceManager()
    with mock.patch("llama_deploy.apiserver.source_managers.git.Repo") as repo_mock:
        sm.sync("source", "dest")
        repo_mock.clone_from.assert_called_with(to_path="dest", url="source")
        sm.sync("source@branch", "dest")
        repo_mock.clone_from.assert_called_with(
            to_path="dest", url="source", multi_options=["-b branch", "--single-branch"]
        )
