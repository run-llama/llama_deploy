import asyncio
from typing import Any, Callable

from llama_agents.messages.base import QueueMessage
from llama_agents.message_consumers.base import BaseMessageQueueConsumer


class CallableMessageConsumer(BaseMessageQueueConsumer):
    handler: Callable

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        if asyncio.iscoroutinefunction(self.handler):
            await self.handler(message, **kwargs)
        else:
            self.handler(message, **kwargs)
