from unittest import mock

import pytest

from llama_deploy.control_plane import ControlPlaneConfig
from llama_deploy.control_plane.config import parse_state_store_uri


def test_config_url() -> None:
    cfg = ControlPlaneConfig(host="localhost", port=4242)
    assert cfg.url == "http://localhost:4242"
    cfg = ControlPlaneConfig(host="localhost", port=4242, use_tls=True)
    assert cfg.url == "https://localhost:4242"


def test_parse_state_store_uri_malformed() -> None:
    with pytest.raises(ValueError, match="key-value store '' is not supported."):
        parse_state_store_uri("some_wrong_uri")

    with pytest.raises(ValueError, match="key-value store 'foo' is not supported."):
        parse_state_store_uri("foo://user:pass@host/database")


# Ensure the module is never available, even if the package is installed
@mock.patch.dict("sys.modules", {"llama_index.storage.kvstore.redis": None})
def test_parse_state_store_uri_redis_not_installed() -> None:
    with pytest.raises(
        ValueError, match="pip install llama-index-storage-kvstore-redis"
    ):
        parse_state_store_uri("redis://localhost/")


def test_parse_state_store_uri_redis() -> None:
    redis_mock = mock.MagicMock()

    with mock.patch.dict(
        "sys.modules", {"llama_index.storage.kvstore.redis": redis_mock}
    ):
        parse_state_store_uri("redis://localhost/")
        calls = redis_mock.mock_calls
        assert len(calls) == 1
        assert calls[0].kwargs == {"redis_uri": "redis://localhost/"}


# Ensure the module is never available, even if the package is installed
@mock.patch.dict("sys.modules", {"llama_index.storage.kvstore.mongodb": None})
def test_parse_state_store_uri_mongodb_not_installed() -> None:
    with pytest.raises(
        ValueError, match="pip install llama-index-storage-kvstore-mongodb"
    ):
        parse_state_store_uri("mongodb+srv://localhost/")


def test_parse_state_store_uri_mongodb() -> None:
    redis_mock = mock.MagicMock()

    with mock.patch.dict(
        "sys.modules", {"llama_index.storage.kvstore.mongodb": redis_mock}
    ):
        parse_state_store_uri("mongodb+srv://localhost/")
        calls = redis_mock.mock_calls
        assert len(calls) == 1
        assert calls[0].kwargs == {"uri": "mongodb+srv://localhost/"}
