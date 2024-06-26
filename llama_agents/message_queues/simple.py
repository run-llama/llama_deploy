"""Simple Message Queue."""

import asyncio
import httpx
import random
import uvicorn

from collections import deque
from contextlib import asynccontextmanager
from fastapi import FastAPI
from logging import getLogger
from pydantic import Field, PrivateAttr
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import urljoin

from llama_agents.message_queues.base import BaseMessageQueue
from llama_agents.messages.base import QueueMessage
from llama_agents.message_consumers.base import BaseMessageQueueConsumer
from llama_agents.message_consumers.remote import (
    RemoteMessageConsumer,
    RemoteMessageConsumerDef,
)
from llama_agents.types import PydanticValidatedUrl

logger = getLogger(__name__)


class SimpleRemoteClientMessageQueue(BaseMessageQueue):
    """Remote client to be used with a SimpleMessageQueue server."""

    base_url: PydanticValidatedUrl
    client_kwargs: Optional[Dict] = None
    client: Optional[httpx.AsyncClient] = None

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
    ) -> httpx.Response:
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
        return result

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


class SimpleMessageQueue(BaseMessageQueue):
    """SimpleMessageQueue.

    An in-memory message queue that implements a push model for consumers.
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
        port: int = 8001,
    ):
        super().__init__(consumers=consumers, queues=queues, host=host, port=port)

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
        base_url = f"http://{self.host}:{self.port}"
        return SimpleRemoteClientMessageQueue(base_url=base_url)

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
    ) -> None:
        """Register a new consumer."""
        message_type_str = consumer.message_type

        if message_type_str not in self.consumers:
            self.consumers[message_type_str] = {consumer.id_: consumer}
            logger.info(
                f"Consumer {consumer.id_}: {message_type_str} has been registered."
            )
        else:
            if consumer.id_ in self.consumers[message_type_str]:
                raise ValueError("Consumer has already been added.")

            self.consumers[message_type_str][consumer.id_] = consumer
            logger.info(
                f"Consumer {consumer.id_}: {message_type_str} has been registered."
            )

        if message_type_str not in self.queues:
            self.queues[message_type_str] = deque()

    async def register_remote_consumer(
        self, consumer_def: RemoteMessageConsumerDef
    ) -> Dict[str, str]:
        consumer = RemoteMessageConsumer(**consumer_def.model_dump())
        await self.register_consumer(consumer)
        return {"consumer": consumer.id_}

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> None:
        message_type_str = consumer.message_type
        if consumer.id_ not in self.consumers.get(message_type_str, {}):
            raise ValueError(
                f"No consumer found for associated message type. {consumer.id_}: {message_type_str}"
            )

        del self.consumers[message_type_str][consumer.id_]
        if len(self.consumers[message_type_str]) == 0:
            del self.consumers[message_type_str]

    async def deregister_remote_consumer(
        self, consumer_def: RemoteMessageConsumerDef
    ) -> None:
        consumer = RemoteMessageConsumer(**consumer_def.model_dump())
        await self.deregister_consumer(consumer)

    async def get_consumers(self, message_type: str) -> List[BaseMessageQueueConsumer]:
        if message_type not in self.consumers:
            return []

        return list(self.consumers[message_type].values())

    async def get_consumer_defs(
        self, message_type: str
    ) -> List[RemoteMessageConsumerDef]:
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
        logger.info("Launching message queue locally")
        return asyncio.create_task(self.processing_loop())

    async def launch_server(self) -> None:
        logger.info(f"Launching message queue server at {self.host}:{self.port}")

        # uvicorn.run(self._app, host=self.host, port=self.port)
        class CustomServer(uvicorn.Server):
            def install_signal_handlers(self) -> None:
                pass

        cfg = uvicorn.Config(self._app, host=self.host, port=self.port)
        server = CustomServer(cfg)
        await server.serve()

    async def home(self) -> Dict[str, str]:
        return {
            "service_name": "message_queue",
            "description": "Message queue for multi-agent system",
        }
