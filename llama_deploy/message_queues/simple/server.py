"""Simple Message Queue."""

import asyncio
import random
from collections import deque
from logging import getLogger
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import Field, PrivateAttr

from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
    default_start_consuming_callable,
)
from llama_deploy.message_consumers.remote import (
    RemoteMessageConsumer,
    RemoteMessageConsumerDef,
)
from llama_deploy.message_queues.base import AbstractMessageQueue, BaseMessageQueue
from llama_deploy.messages.base import QueueMessage

from .client import SimpleRemoteClientMessageQueue
from .config import SimpleMessageQueueConfig

logger = getLogger(__name__)


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
    port: int = 8001
    host: str = "127.0.0.1"

    _app: FastAPI = PrivateAttr()

    def __init__(
        self,
        consumers: Dict[str, Dict[str, BaseMessageQueueConsumer]] = {},
        queues: Dict[str, deque] = {},
        host: str = "127.0.0.1",
        port: Optional[int] = 8001,
    ):
        super().__init__(
            consumers=consumers,
            queues=queues,
            host=host,
            port=port,
        )

        self._app = FastAPI()

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
            "/publish/{topic}",
            self._publish,
            methods=["POST"],
            tags=["QueueMessages"],
        )

    @property
    def client(self) -> AbstractMessageQueue:
        """Returns a client for the message queue server."""
        return SimpleRemoteClientMessageQueue(
            SimpleMessageQueueConfig(host=self.host, port=self.port)
        )

    def _select_consumer(self, message: QueueMessage) -> BaseMessageQueueConsumer:
        """Select a single consumer to publish a message to."""
        message_type_str = message.type
        consumer_id = random.choice(list(self.consumers[message_type_str].keys()))
        return self.consumers[message_type_str][consumer_id]

    async def _publish(self, message: QueueMessage, topic: str) -> Any:
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
        self, consumer: BaseMessageQueueConsumer, topic: str | None = None
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

    async def launch_local(self) -> asyncio.Task:
        """Launch the message queue locally, in-process."""
        logger.info("Launching message queue locally")
        return asyncio.create_task(self.processing_loop())

    async def launch_server(self) -> None:
        """Launch the message queue as a FastAPI server."""
        logger.info(f"Launching message queue server at {self.host}:{self.port}")

        # uvicorn.run(self._app, host=self.host, port=self.port)
        class CustomServer(uvicorn.Server):
            def install_signal_handlers(self) -> None:
                pass

        cfg = uvicorn.Config(self._app, host=self.host, port=self.port)
        server = CustomServer(cfg)
        pl_task = asyncio.create_task(self.processing_loop())

        try:
            await server.serve()
        except asyncio.CancelledError:
            self.running = False
            await asyncio.gather(server.shutdown(), pl_task, return_exceptions=True)

    async def home(self) -> Dict[str, str]:
        return {
            "service_name": "message_queue",
            "description": "Message queue for multi-agent system",
        }

    async def cleanup_local(
        self, message_types: List[str], *args: Any, **kwargs: Dict[str, Any]
    ) -> None:
        pass

    def as_config(self) -> SimpleMessageQueueConfig:
        return SimpleMessageQueueConfig(host=self.host, port=self.port)
