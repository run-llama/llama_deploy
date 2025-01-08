from typing import Any

import pytest
from aiobotocore.session import AioSession, ClientCreatorContext
from pydantic import SecretStr

from llama_deploy.message_queues.aws import AWSMessageQueue, AWSMessageQueueConfig


@pytest.fixture
def aws_queue(monkeypatch: Any) -> AWSMessageQueue:
    mq = AWSMessageQueue()
    return mq


@pytest.fixture
def botocore_not_installed(monkeypatch: Any) -> Any:
    """Mock the import mechanism to raise ImportError even when package is installed"""
    # Store the original import
    original_import = __import__

    def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("botocore"):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    # Replace the import mechanism with our mock
    monkeypatch.setattr("builtins.__import__", mock_import)


@pytest.fixture
def aiobotocore_not_installed(monkeypatch: Any) -> Any:
    """Mock the import mechanism to raise ImportError even when package is installed"""
    # Store the original import
    original_import = __import__

    def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("aiobotocore"):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    # Replace the import mechanism with our mock
    monkeypatch.setattr("builtins.__import__", mock_import)


def test_missing_deps(botocore_not_installed: Any) -> None:
    with pytest.raises(ValueError, match="Missing `botocore` package"):
        AWSMessageQueue()


def test__get_aio_session_missing_deps(aiobotocore_not_installed: Any) -> None:
    with pytest.raises(ValueError, match="Missing `aiobotocore`"):
        mq = AWSMessageQueue()
        mq._get_aio_session()


def test__get_aio_session(aws_queue: AWSMessageQueue) -> None:
    mq = AWSMessageQueue()
    assert type(mq._get_aio_session()) is AioSession


def test__get_client() -> None:
    mq = AWSMessageQueue(
        AWSMessageQueueConfig(
            aws_access_key_id=SecretStr("secret"),
            aws_secret_access_key=SecretStr("moar_secret"),
        )
    )
    assert type(mq._get_client("test_service")) is ClientCreatorContext
