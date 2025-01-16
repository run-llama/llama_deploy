"""Simple Message Queue."""

import asyncio
import logging
from collections import deque
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, HTTPException, status

from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
)
from llama_deploy.messages.base import QueueMessage

from .config import SimpleMessageQueueConfig

logger = logging.getLogger(__name__)


class MessagesPollFilter(logging.Filter):
    """Filters out access logs for /messages/.

    The message queue client works with plain HTTP and as a form of pubsub
    subscription indefintely polls the /messages/ endpoint on the server. To
    avoid cluttering the logs, we filter out GET requests on that specific
    endpoint.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return "GET /messages/" not in record.getMessage()


uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.addFilter(MessagesPollFilter())


class SimpleMessageQueueServer:
    """SimpleMessageQueueServer.

    An in-memory message queue that implements a push model for consumers.

    When registering, a specific queue for a consumer is created.
    When a message is published, it is added to the queue for the given message type.

    When launched as a server, exposes the following endpoints:
    - GET `/`: Home endpoint
    - POST `/register_consumer`: Register a consumer
    - POST `/deregister_consumer`: Deregister a consumer
    - GET `/get_consumers/{message_type}`: Get consumers for a message type
    - POST `/publish`: Publish a message
    """

    def __init__(self, config: SimpleMessageQueueConfig = SimpleMessageQueueConfig()):
        self._config = config
        self._consumers: dict[str, dict[str, BaseMessageQueueConsumer]] = {}
        self._queues: dict[str, deque] = {}
        self._running = False
        self._app = FastAPI()

        self._app.add_api_route(
            "/",
            self._home,
            methods=["GET"],
        )
        self._app.add_api_route(
            "/topics/{topic}",
            self._create_topic,
            methods=["POST"],
        )
        self._app.add_api_route(
            "/messages/{topic}",
            self._publish,
            methods=["POST"],
        )
        self._app.add_api_route(
            "/messages/{topic}",
            self._get_messages,
            methods=["GET"],
        )

    async def launch_server(self) -> None:
        """Launch the message queue as a FastAPI server."""
        logger.info(f"Launching message queue server at {self._config.base_url}")
        self._running = True

        cfg = uvicorn.Config(
            self._app, host=self._config.host, port=self._config.port or 80
        )
        server = uvicorn.Server(cfg)

        try:
            await server.serve()
        except asyncio.CancelledError:
            self._running = False
            await asyncio.gather(server.shutdown(), return_exceptions=True)

    #
    # HTTP API endpoints
    #

    async def _home(self) -> Dict[str, str]:
        return {
            "service_name": "message_queue",
            "description": "Message queue for multi-agent system",
        }

    async def _create_topic(self, topic: str) -> Any:
        if topic in self._queues:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A consumer with the same url has previously been registered.",
            )

        self._queues[topic] = deque()

    async def _publish(self, message: QueueMessage, topic: str) -> Any:
        """Publish message to a queue."""
        if topic not in self._queues:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"topic {topic} not found"
            )

        self._queues[topic].append(message)

    async def _get_messages(self, topic: str) -> QueueMessage | None:
        if topic not in self._queues:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"topic {topic} not found"
            )
        if queue := self._queues[topic]:
            message: QueueMessage = queue.popleft()
            return message

        return None
