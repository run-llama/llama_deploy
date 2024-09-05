"""Simple Message Queue."""

import asyncio
import httpx
import random
import uvicorn

from collections import deque
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from logging import getLogger
from pydantic import BaseModel, Field, PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import urljoin

from llama_deploy.message_queues.base import BaseMessageQueue
from llama_deploy.messages.base import QueueMessage
from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
    default_start_consuming_callable,
)
from llama_deploy.message_consumers.remote import (
    RemoteMessageConsumer,
    RemoteMessageConsumerDef,
)
from llama_deploy.types import PydanticValidatedUrl

logger = getLogger(__name__)


class SimpleMessageQueueConfig(BaseSettings):
    """Simple message queue configuration."""

    model_config = SettingsConfigDict(env_prefix="SIMPLE_MESSAGE_QUEUE_")

    host: str = "127.0.0.1"
    port: Optional[int] = 8001
    internal_host: Optional[str] = None
    internal_port: Optional[int] = None


class SimpleRemoteClientMessageQueue(BaseMessageQueue):
    """Remote client to be used with a SimpleMessageQueue server."""

    base_url: PydanticValidatedUrl
    host: str
    port: Optional[int]
    client_kwargs: Optional[Dict] = None
    client: Optional[httpx.AsyncClient] = None
    raise_exceptions: bool = False

    async def _publish(
        self, message: QueueMessage, publish_url: str = "publish", **kwargs: Any
    ) -> Any:
        client_kwargs = self.client_kwargs or {}
        url = urljoin(self.base_url, publish_url)
        async with httpx.AsyncClient(**client_kwargs) as client:
            result = await client.post(url, json=message.model_dump())
        return result

    async def register_consumer(
        self,
        consumer: BaseMessageQueueConsumer,
        register_consumer_url: str = "register_consumer",
        **kwargs: Any,
    ) -> StartConsumingCallable:
        client_kwargs = self.client_kwargs or {}
        url = urljoin(self.base_url, register_consumer_url)
        try:
            remote_consumer_def = RemoteMessageConsumerDef(**consumer.model_dump())
        except Exception as e:
            raise ValueError(
                "Unable to convert consumer to RemoteMessageConsumer"
            ) from e
        async with httpx.AsyncClient(**client_kwargs) as client:
            result = await client.post(url, json=remote_consumer_def.model_dump())
        if result.status_code != status.HTTP_200_OK:
            logger.debug(
                f"An error occurred in registering consumer: {result.status_code}"
            )
            if self.raise_exceptions:
                raise ValueError(
                    f"An error occurred in registering consumer: {result.status_code}"
                )
        return default_start_consuming_callable

    async def deregister_consumer(
        self,
        consumer: BaseMessageQueueConsumer,
        deregister_consumer_url: str = "deregister_consumer",
    ) -> Any:
        client_kwargs = self.client_kwargs or {}
        url = urljoin(self.base_url, deregister_consumer_url)
        try:
            remote_consumer_def = RemoteMessageConsumerDef(**consumer.model_dump())
        except Exception as e:
            raise ValueError(
                "Unable to convert consumer to RemoteMessageConsumer"
            ) from e
        async with httpx.AsyncClient(**client_kwargs) as client:
            result = await client.post(url, json=remote_consumer_def.model_dump())
        return result

    async def get_consumers(
        self, message_type: str, get_consumers_url: str = "get_consumers"
    ) -> List[BaseMessageQueueConsumer]:
        client_kwargs = self.client_kwargs or {}
        url = urljoin(self.base_url, f"{get_consumers_url}/{message_type}")
        async with httpx.AsyncClient(**client_kwargs) as client:
            res = await client.get(url)
        if res.status_code == 200:
            remote_consumer_defs = res.json()
            consumers = [RemoteMessageConsumer(**el) for el in remote_consumer_defs]
        else:
            consumers = []
        return consumers

    async def processing_loop(self) -> None:
        raise NotImplementedError(
            "`procesing_loop()` is not implemented for this class."
        )

    async def launch_local(self) -> asyncio.Task:
        raise NotImplementedError("`launch_local()` is not implemented for this class.")

    async def launch_server(self) -> None:
        raise NotImplementedError(
            "`launch_server()` is not implemented for this class."
        )

    async def cleanup_local(
        self, message_types: List[str], *args: Any, **kwargs: Dict[str, Any]
    ) -> None:
        raise NotImplementedError(
            "`cleanup_local()` is not implemented for this class."
        )

    def as_config(self) -> Dict[str, dict]:
        return SimpleMessageQueueConfig(host=self.host, port=self.port)


class SimpleMessageQueue(BaseMessageQueue):
    """SimpleMessageQueue.

    An in-memory message queue that implements a push model for consumers.

    When registering, a specific queue for a consumer is created.
    When a message is published, it is added to the queue for the given message type.

    When launched as a server, exposes the following endpoints:
    - GET `/`: Home endpoint
    - POST `/register_consumer`: Register a consumer
    - POST `/deregister_consumer`: Deregister a consumer
    - GET `/get_consumers/{message_type}`: Get consumers for a message type
    - POST `/publish`: Publish a message

    Attributes:
        consumers (Dict[str, Dict[str, BaseMessageQueueConsumer]]):
            A dictionary of message type to consumer id to consumer.
        queues (Dict[str, deque]):
            A dictionary of message type to queue.
        running (bool):
            Whether the message queue is running.
        port (Optional[int]):
            The port to run the message queue server on.
        host (str):
            The host to run the message queue server on.
    """

    consumers: Dict[str, Dict[str, BaseMessageQueueConsumer]] = Field(
        default_factory=dict
    )
    queues: Dict[str, deque] = Field(default_factory=dict)
    running: bool = True
    port: Optional[int] = 8001
    host: str = "127.0.0.1"
    internal_host: Optional[str] = None
    internal_port: Optional[int] = None

    _app: FastAPI = PrivateAttr()

    def __init__(
        self,
        consumers: Dict[str, Dict[str, BaseMessageQueueConsumer]] = {},
        queues: Dict[str, deque] = {},
        host: str = "127.0.0.1",
        port: Optional[int] = 8001,
        internal_host: Optional[str] = None,
        internal_port: Optional[int] = None,
    ):
        super().__init__(
            consumers=consumers,
            queues=queues,
            host=host,
            port=port,
            internal_host=internal_host,
            internal_port=internal_port,
        )

        self._app = FastAPI(lifespan=self.lifespan)

        self._app.add_api_route(
            "/", self.home, methods=["GET"], tags=["Message Queue State"]
        )

        self._app.add_api_route(
            "/register_consumer",
            self.register_remote_consumer,
            methods=["POST"],
            tags=["Consumers"],
        )

        self._app.add_api_route(
            "/deregister_consumer",
            self.deregister_remote_consumer,
            methods=["POST"],
            tags=["Consumers"],
        )

        self._app.add_api_route(
            "/get_consumers/{message_type}",
            self.get_consumer_defs,
            methods=["GET"],
            tags=["Consumers"],
        )

        self._app.add_api_route(
            "/publish",
            self._publish,
            methods=["POST"],
            tags=["QueueMessages"],
        )

    @property
    def client(self) -> BaseMessageQueue:
        """Returns a client for the message queue server."""
        base_url = (
            f"http://{self.host}:{self.port}" if self.port else f"http://{self.host}"
        )
        return SimpleRemoteClientMessageQueue(
            base_url=base_url,
            host=self.host,
            port=self.port,
        )

    def _select_consumer(self, message: QueueMessage) -> BaseMessageQueueConsumer:
        """Select a single consumer to publish a message to."""
        message_type_str = message.type
        consumer_id = random.choice(list(self.consumers[message_type_str].keys()))
        return self.consumers[message_type_str][consumer_id]

    async def _publish(self, message: QueueMessage) -> Any:
        """Publish message to a queue."""
        message_type_str = message.type

        if message_type_str not in self.consumers:
            logger.debug(
                f"Failed to publish message. No registered consumer '{message_type_str}'."
            )
            raise ValueError(
                f"No consumer for '{message_type_str}' has been registered."
            )

        if message_type_str not in self.queues:
            self.queues[message_type_str] = deque()

        self.queues[message_type_str].append(message)

    async def _publish_to_consumer(self, message: QueueMessage, **kwargs: Any) -> Any:
        """Publish message to a consumer."""
        consumer = self._select_consumer(message)
        try:
            await consumer.process_message(message, **kwargs)
            logger.info(f"Successfully published message '{message.type}' to consumer.")
        except Exception as e:
            logger.debug(
                f"Failed to publish message of type '{message.type}' to consumer. Message: {str(e)}"
            )
            raise

    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer, **kwargs: Any
    ) -> StartConsumingCallable:
        """Register a new consumer."""
        message_type_str = consumer.message_type

        if message_type_str not in self.consumers:
            self.consumers[message_type_str] = {consumer.id_: consumer}
            logger.info(
                f"Consumer {consumer.id_}: {message_type_str} has been registered."
            )
        else:
            if consumer.id_ in self.consumers[message_type_str]:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Consumer with the same id_ has already been previously added.",
                )
            self.consumers[message_type_str][consumer.id_] = consumer
            logger.info(
                f"Consumer {consumer.id_}: {message_type_str} has been registered."
            )

        if message_type_str not in self.queues:
            self.queues[message_type_str] = deque()
        return default_start_consuming_callable

    async def register_remote_consumer(
        self, consumer_def: RemoteMessageConsumerDef
    ) -> Dict[str, str]:
        """API endpoint to register a consumer based on a consumer definition."""
        consumer = RemoteMessageConsumer(**consumer_def.model_dump())
        message_type = consumer.message_type

        # check if consumer with same url already exists
        if message_type in self.consumers:

            def consumer_with_same_url(
                c: RemoteMessageConsumer,
            ) -> bool:
                return c.url == consumer.url

            try:
                next(
                    filter(
                        consumer_with_same_url,
                        [
                            c
                            for c in self.consumers[message_type].values()
                            if isinstance(c, RemoteMessageConsumer)
                        ],
                    )
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A consumer with the same url has previously been registered.",
                )
            except StopIteration:
                pass

        await self.register_consumer(consumer)
        return {"consumer": consumer.id_}

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> None:
        """Deregister a consumer."""
        message_type_str = consumer.message_type
        if consumer.id_ not in self.consumers.get(message_type_str, {}):
            raise HTTPException(
                detail=f"No consumer found for associated message type. {consumer.id_}: {message_type_str}",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        del self.consumers[message_type_str][consumer.id_]
        if len(self.consumers[message_type_str]) == 0:
            del self.consumers[message_type_str]

    async def deregister_remote_consumer(
        self, consumer_def: RemoteMessageConsumerDef
    ) -> None:
        """API endpoint to deregister a consumer based on a consumer definition."""
        consumer = RemoteMessageConsumer(**consumer_def.model_dump())
        await self.deregister_consumer(consumer)

    async def get_consumers(self, message_type: str) -> List[BaseMessageQueueConsumer]:
        """Get all consumersm for a given type."""
        if message_type not in self.consumers:
            return []

        return list(self.consumers[message_type].values())

    async def get_consumer_defs(
        self, message_type: str
    ) -> List[RemoteMessageConsumerDef]:
        """Get all consumer definitions for a given type."""
        if message_type not in self.consumers:
            return []

        return [
            RemoteMessageConsumerDef(**c.model_dump())
            for c in self.consumers[message_type].values()
        ]

    async def processing_loop(self) -> None:
        """A loop for getting messages from queues and sending to consumer."""
        while self.running:
            for queue in self.queues.values():
                if queue:
                    message: QueueMessage = queue.popleft()
                    message.stats.process_start_time = message.stats.timestamp_str()
                    await self._publish_to_consumer(message)
                    message.stats.process_end_time = (
                        message.stats.timestamp_str()
                    )  # TODO dedicated ack
            await asyncio.sleep(0.1)

    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncGenerator[None, None]:
        """Starts the processing loop when the fastapi app starts."""
        asyncio.create_task(self.processing_loop())
        yield
        self.running = False

    async def launch_local(self) -> asyncio.Task:
        """Launch the message queue locally, in-process."""
        logger.info("Launching message queue locally")
        return asyncio.create_task(self.processing_loop())

    async def launch_server(self) -> None:
        """Launch the message queue as a FastAPI server."""
        host = self.internal_host or self.host
        port = self.internal_port or self.port
        logger.info(f"Launching message queue server at {host}:{port}")

        # uvicorn.run(self._app, host=self.host, port=self.port)
        class CustomServer(uvicorn.Server):
            def install_signal_handlers(self) -> None:
                pass

        cfg = uvicorn.Config(self._app, host=host, port=port)
        server = CustomServer(cfg)
        await server.serve()

    async def home(self) -> Dict[str, str]:
        return {
            "service_name": "message_queue",
            "description": "Message queue for multi-agent system",
        }

    async def cleanup_local(
        self, message_types: List[str], *args: Any, **kwargs: Dict[str, Any]
    ) -> None:
        pass

    def as_config(self) -> BaseModel:
        return SimpleMessageQueueConfig(
            host=self.host,
            port=self.port,
            internal_host=self.internal_host,
            internal_port=self.internal_port,
        )


if __name__ == "__main__":
    mq = SimpleMessageQueue()
    asyncio.run(mq.launch_server())
