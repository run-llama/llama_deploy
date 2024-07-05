import json
from pathlib import Path
from typing import Dict, Optional
from llama_agents import (
    CallableMessageConsumer,
    QueueMessage,
)
from fastapi import FastAPI
from llama_agents.message_queues.base import BaseMessageQueue
from llama_agents.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)
from llama_agents.message_consumers.remote import RemoteMessageConsumer
from logging import getLogger

logger = getLogger(__name__)


class TaskResultService:
    def __init__(
        self,
        message_queue: BaseMessageQueue,
        name: str = "human",
        host: str = "127.0.0.1",
        port: Optional[int] = 8000,
    ) -> None:
        self.name = name
        self.host = host
        self.port = port

        self._message_queue = message_queue

        # app
        self._app = FastAPI()
        self._app.add_api_route(
            "/", self.home, methods=["GET"], tags=["Human Consumer"]
        )
        self._app.add_api_route(
            "/process_message",
            self.process_message,
            methods=["POST"],
            tags=["Human Consumer"],
        )

    @property
    def message_queue(self) -> BaseMessageQueue:
        return self._message_queue

    def as_consumer(self, remote: bool = False) -> BaseMessageQueueConsumer:
        if remote:
            return RemoteMessageConsumer(
                url=(
                    f"http://{self.host}:{self.port}/process_message"
                    if self.port
                    else f"http://{self.host}/process_message"
                ),
                message_type=self.name,
            )

        return CallableMessageConsumer(
            message_type=self.name,
            handler=self.process_message,
        )

    async def process_message(self, message: QueueMessage) -> None:
        Path("task_results").mkdir(exist_ok=True)
        with open("task_results/task_results.jsonl", "+a") as f:
            json.dump(message.model_dump(), f)
            f.write("\n")

    async def home(self) -> Dict[str, str]:
        return {"message": "hello, human."}

    async def register_to_message_queue(self) -> StartConsumingCallable:
        """Register to the message queue."""
        return await self.message_queue.register_consumer(self.as_consumer(remote=True))
