import asyncio
from typing import Any, Callable

from llama_deploy.messages.base import QueueMessage
from llama_deploy.message_consumers.base import BaseMessageQueueConsumer


class CallableMessageConsumer(BaseMessageQueueConsumer):
    """Message consumer for a callable handler.

    For a given message, it will call the handler with the message as input.
    """

    handler: Callable

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        if asyncio.iscoroutinefunction(self.handler):
            await self.handler(message, **kwargs)
        else:
            self.handler(message, **kwargs)
