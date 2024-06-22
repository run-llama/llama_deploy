"""Remote message queue."""

import httpx
import logging
from typing import Any, Dict, List, Optional

from agentfile.message_queues.base import BaseMessageQueue
from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.messages import QueueMessage

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


class RemoteMessageQueue(BaseMessageQueue):
    url: str
    client_kwargs: Optional[Dict] = None
    client: Optional[httpx.AsyncClient] = None

    async def _publish(self, message: QueueMessage, **kwargs: Any) -> Any:
        ...

    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer, **kwargs: Any
    ) -> Any:
        ...

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> Any:
        ...

    async def get_consumers(self, message_type: str) -> List[BaseMessageQueueConsumer]:
        return []

    async def processing_loop(self) -> None:
        pass

    async def launch_local(self) -> None:
        pass

    def launch_server(self) -> None:
        ...
