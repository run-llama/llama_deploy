from typing import Any, Callable

from agentfile.messages.base import QueueMessage
from agentfile.message_consumers.base import BaseMessageQueueConsumer


class CallableMessageConsumer(BaseMessageQueueConsumer):
    handler: Callable

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        return await self.handler(message, **kwargs)
