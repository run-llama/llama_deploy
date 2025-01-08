import logging
from typing import Any
from unittest import mock

import pytest
import pytest_asyncio
from aiobotocore.session import AioSession
from botocore.exceptions import ClientError
from pydantic import SecretStr

from llama_deploy.message_queues.aws import AWSMessageQueue, AWSMessageQueueConfig


@pytest_asyncio.fixture
async def aws_queue(monkeypatch: Any) -> Any:
    mq = AWSMessageQueue()
    yield mq
    await mq.cleanup()


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


def test_ctor(caplog) -> None:
    caplog.set_level(logging.INFO, logger="llama_deploy.message_queues.aws")
    AWSMessageQueue(AWSMessageQueueConfig(aws_access_key_id=SecretStr("")))
    assert "Using default AWS credential provider chain" in caplog.text


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


@pytest.mark.asyncio
async def test__get_client() -> None:
    mq = AWSMessageQueue(
        AWSMessageQueueConfig(
            aws_access_key_id=SecretStr("secret"),
            aws_secret_access_key=SecretStr("moar_secret"),
        )
    )
    async with mq._get_client("sns") as client:
        assert client


@pytest.mark.asyncio
async def test_get_topic_by_name(aws_queue: AWSMessageQueue) -> None:
    mock_response = {
        "Topics": [{"TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic.fifo"}]
    }

    class MockSNSClient:
        def __init__(self, should_raise: bool = False):
            self.should_raise = should_raise

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def list_topics(self):
            if self.should_raise:
                raise ClientError(
                    operation_name="list_topics",
                    error_response={
                        "Error": {
                            "Code": "InternalError",
                            "Message": "AWS Internal Error",
                        }
                    },
                )
            return mock_response

    aws_queue._get_client = lambda x: MockSNSClient()  # type: ignore
    topic = await aws_queue.get_topic_by_name("test-topic")
    assert topic.arn == "arn:aws:sns:us-east-1:123456789012:test-topic.fifo"
    assert topic.name == "test-topic"

    mock_response["Topics"] = []
    with pytest.raises(ValueError, match="Could not find topic test-topic"):
        await aws_queue.get_topic_by_name("test-topic")

    # Test ClientError exception
    aws_queue._get_client = lambda x: MockSNSClient(should_raise=True)  # type: ignore
    with pytest.raises(ClientError, match="AWS Internal Error"):
        await aws_queue.get_topic_by_name("test-topic")


@pytest.mark.asyncio
async def test_create_sns_topic(aws_queue: AWSMessageQueue) -> None:
    from botocore.exceptions import ClientError

    # Mock responses
    existing_topic_response = {
        "Topics": [
            {"TopicArn": "arn:aws:sns:us-east-1:123456789012:existing-topic.fifo"}
        ]
    }

    new_topic_response = {
        "TopicArn": "arn:aws:sns:us-east-1:123456789012:new-topic.fifo"
    }

    class MockSNSClient:
        def __init__(self, should_raise: bool = False):
            self.should_raise = should_raise
            self.create_topic_called = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def delete_topic(self, *args, **kwargs):
            pass

        async def list_topics(self):
            if self.should_raise:
                raise ClientError(
                    operation_name="list_topics",
                    error_response={
                        "Error": {
                            "Code": "InternalError",
                            "Message": "AWS Internal Error",
                        }
                    },
                )
            return existing_topic_response

        async def create_topic(self, Name: str, Attributes: dict):
            self.create_topic_called = True
            if self.should_raise:
                raise ClientError(
                    operation_name="create_topic",
                    error_response={
                        "Error": {
                            "Code": "InternalError",
                            "Message": "AWS Internal Error",
                        }
                    },
                )
            return new_topic_response

    # Test finding existing topic
    mock_client = MockSNSClient()
    aws_queue._get_client = lambda x: mock_client  # type: ignore

    topic = await aws_queue._create_sns_topic("existing-topic")
    assert topic.arn == "arn:aws:sns:us-east-1:123456789012:existing-topic.fifo"
    assert topic.name == "existing-topic"
    assert not mock_client.create_topic_called

    # Test creating new topic
    existing_topic_response["Topics"] = []  # Clear existing topics
    topic = await aws_queue._create_sns_topic("new-topic")
    assert topic.arn == "arn:aws:sns:us-east-1:123456789012:new-topic.fifo"
    assert topic.name == "new-topic"
    assert mock_client.create_topic_called
    assert topic in aws_queue._topics

    # Test ClientError during list_topics
    mock_client = MockSNSClient(should_raise=True)
    aws_queue._get_client = lambda x: mock_client  # type: ignore

    with pytest.raises(ClientError, match="AWS Internal Error"):
        await aws_queue._create_sns_topic("error-topic")

    # Test ClientError during create_topic
    mock_client = MockSNSClient(should_raise=True)
    aws_queue._get_client = lambda x: mock_client  # type: ignore
    existing_topic_response["Topics"] = []  # Force create_topic to be called

    with pytest.raises(ClientError, match="AWS Internal Error"):
        await aws_queue._create_sns_topic("error-topic")


@pytest.mark.asyncio
async def test_create_sqs_queue(aws_queue: AWSMessageQueue) -> None:
    from botocore.exceptions import ClientError

    # Mock responses
    existing_queue_response = {
        "QueueUrls": [
            "https://sqs.us-east-1.amazonaws.com/123456789012/existing-queue.fifo"
        ]
    }

    new_queue_response = {
        "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/new-queue.fifo"
    }

    queue_attributes_response = {
        "Attributes": {"QueueArn": "arn:aws:sqs:us-east-1:123456789012:test-queue.fifo"}
    }

    class MockSQSClient:
        def __init__(self, should_raise: bool = False):
            self.should_raise = should_raise
            self.create_queue_called = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def delete_queue(self, *args, **kwargs):
            pass

        async def list_queues(self, QueueNamePrefix: str):
            if self.should_raise:
                raise ClientError(
                    operation_name="list_queues",
                    error_response={
                        "Error": {
                            "Code": "InternalError",
                            "Message": "AWS Internal Error",
                        }
                    },
                )
            return existing_queue_response

        async def create_queue(self, QueueName: str, Attributes: dict):
            self.create_queue_called = True
            if self.should_raise:
                raise ClientError(
                    operation_name="create_queue",
                    error_response={
                        "Error": {
                            "Code": "InternalError",
                            "Message": "AWS Internal Error",
                        }
                    },
                )
            return new_queue_response

        async def get_queue_attributes(self, QueueUrl: str, AttributeNames: list):
            if self.should_raise:
                raise ClientError(
                    operation_name="get_queue_attributes",
                    error_response={
                        "Error": {
                            "Code": "InternalError",
                            "Message": "AWS Internal Error",
                        }
                    },
                )
            return queue_attributes_response

    # Test finding existing queue
    mock_client = MockSQSClient()
    aws_queue._get_client = lambda x: mock_client  # type: ignore

    queue = await aws_queue._create_sqs_queue("existing-queue")
    assert (
        queue.url
        == "https://sqs.us-east-1.amazonaws.com/123456789012/existing-queue.fifo"
    )
    assert queue.arn == "arn:aws:sqs:us-east-1:123456789012:test-queue.fifo"
    assert queue.name == "existing-queue"
    assert not mock_client.create_queue_called
    assert queue in aws_queue._queues

    # Test creating new queue
    existing_queue_response["QueueUrls"] = []  # Clear existing queues
    queue = await aws_queue._create_sqs_queue("new-queue")
    assert (
        queue.url == "https://sqs.us-east-1.amazonaws.com/123456789012/new-queue.fifo"
    )
    assert queue.arn == "arn:aws:sqs:us-east-1:123456789012:test-queue.fifo"
    assert queue.name == "new-queue"
    assert mock_client.create_queue_called

    # Test ClientError during list_queues
    mock_client = MockSQSClient(should_raise=True)
    aws_queue._get_client = lambda x: mock_client  # type: ignore

    with pytest.raises(ClientError, match="AWS Internal Error"):
        await aws_queue._create_sqs_queue("error-queue")

    # Test ClientError during create_queue
    mock_client = MockSQSClient(should_raise=True)
    aws_queue._get_client = lambda x: mock_client  # type: ignore
    existing_queue_response["QueueUrls"] = []  # Force create_queue to be called

    with pytest.raises(ClientError, match="AWS Internal Error"):
        await aws_queue._create_sqs_queue("error-queue")

    # Test ClientError during get_queue_attributes
    mock_client = MockSQSClient(should_raise=True)
    aws_queue._get_client = lambda x: mock_client  # type: ignore

    with pytest.raises(ClientError, match="AWS Internal Error"):
        await aws_queue._create_sqs_queue("error-queue")


@pytest.mark.asyncio
async def test_update_queue_policy(aws_queue: AWSMessageQueue) -> None:
    class MockSQSClient:
        def __init__(self, should_raise: bool = False):
            self.should_raise = should_raise
            self.set_queue_attributes_called = False
            self.last_policy = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def set_queue_attributes(self, QueueUrl: str, Attributes: dict):
            self.set_queue_attributes_called = True
            self.last_policy = Attributes.get("Policy")

    # Test successful policy update
    mock_client = MockSQSClient()
    aws_queue._get_client = lambda x: mock_client  # type: ignore

    await aws_queue._update_queue_policy(
        mock.MagicMock(arn="foo_arn"), mock.MagicMock(arn="bar_arn")
    )  # type: ignore
    assert mock_client.set_queue_attributes_called


@pytest.mark.asyncio
async def test_subscribe_queue_to_topic(aws_queue: AWSMessageQueue) -> None:
    from botocore.exceptions import ClientError

    class MockSNSClient:
        def __init__(self, should_raise: bool = False):
            self.should_raise = should_raise
            self.subscribe_called = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def subscribe(self, TopicArn: str, Protocol: str, Endpoint: str):
            self.subscribe_called = True
            if self.should_raise:
                raise ClientError(
                    operation_name="subscribe",
                    error_response={
                        "Error": {
                            "Code": "InternalError",
                            "Message": "AWS Internal Error",
                        }
                    },
                )
            return {
                "SubscriptionArn": "arn:aws:sns:us-east-1:123456789012:test-topic:subscription-id"
            }

    # Mock for _update_queue_policy
    update_policy_called = False

    async def mock_update_queue_policy(queue, topic):  # type: ignore
        nonlocal update_policy_called
        update_policy_called = True

    # Test successful subscription
    mock_client = MockSNSClient()
    aws_queue._get_client = lambda x: mock_client  # type: ignore
    aws_queue._update_queue_policy = mock_update_queue_policy  # type: ignore

    subscription = await aws_queue._subscribe_queue_to_topic(
        mock.MagicMock(arn="foo_arn"), mock.MagicMock(arn="bar_arn")
    )

    assert mock_client.subscribe_called
    assert update_policy_called
    assert (
        subscription.arn
        == "arn:aws:sns:us-east-1:123456789012:test-topic:subscription-id"
    )
    assert subscription in aws_queue._subscriptions

    # Test ClientError during subscribe
    mock_client = MockSNSClient(should_raise=True)
    aws_queue._get_client = lambda x: mock_client  # type: ignore
    update_policy_called = False

    with pytest.raises(ClientError, match="AWS Internal Error"):
        await aws_queue._subscribe_queue_to_topic(
            mock.MagicMock(arn="foo_arn"), mock.MagicMock(arn="bar_arn")
        )
    # Policy update shouldn't be called if subscription fails
    assert not update_policy_called
