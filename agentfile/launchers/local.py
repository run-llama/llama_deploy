import asyncio
import uuid
from typing import Any, Callable, Dict, List, Optional

from agentfile.agent_server.base import BaseAgentServer
from agentfile.control_plane.base import BaseControlPlane
from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.message_queues.simple import SimpleMessageQueue
from agentfile.message_queues.base import PublishCallback
from agentfile.messages.base import QueueMessage
from agentfile.types import ActionTypes, TaskDefinition
from agentfile.message_publishers.publisher import MessageQueuePublisherMixin


class HumanMessageConsumer(BaseMessageQueueConsumer):
    message_handler: Dict[str, Callable]
    message_type: str = "human"

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        action = message.action
        if action not in self.message_handler:
            raise ValueError(f"Action {action} not supported by control plane")

        if action == ActionTypes.COMPLETED_TASK:
            await self.message_handler[action](message_data=message.data)


class LocalLauncher(MessageQueuePublisherMixin):
    def __init__(
        self,
        agent_servers: List[BaseAgentServer],
        control_plane: BaseControlPlane,
        message_queue: SimpleMessageQueue,
        publish_callback: Optional[PublishCallback] = None,
    ) -> None:
        self.agent_servers = agent_servers
        self.control_plane = control_plane
        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback

    @property
    def message_queue(self) -> SimpleMessageQueue:
        return self._message_queue

    @property
    def publisher_id(self) -> str:
        return self._publisher_id

    @property
    def publish_callback(self) -> Optional[PublishCallback]:
        return self._publish_callback

    async def handle_human_message(self, **kwargs: Any) -> None:
        message_data = kwargs["message_data"]
        result = (
            message_data["result"] if "result" in message_data else str(message_data)
        )
        print("Got response:\n", result, flush=True)

    async def register_consumers(
        self, consumers: Optional[List[BaseMessageQueueConsumer]] = None
    ) -> None:
        for agent_server in self.agent_servers:
            await self.message_queue.register_consumer(agent_server.get_consumer())

        consumers = consumers or []
        for consumer in consumers:
            await self.message_queue.register_consumer(consumer)

        await self.message_queue.register_consumer(self.control_plane.get_consumer())

    def launch_single(self, initial_task: str) -> None:
        asyncio.run(self.alaunch_single(initial_task))

    async def alaunch_single(self, initial_task: str) -> None:
        # register human consumer
        human_consumer = HumanMessageConsumer(
            message_handler={
                ActionTypes.COMPLETED_TASK: self.handle_human_message,
            }
        )
        await self.register_consumers([human_consumer])

        # publish initial task
        await self.publish(
            QueueMessage(
                publisher_id=self.publisher_id,
                type="control_plane",
                action=ActionTypes.NEW_TASK,
                data=TaskDefinition(input=initial_task).dict(),
            ),
            callback=self.publish_callback,
        )

        # register each agent to the control plane
        for agent_server in self.agent_servers:
            await self.control_plane.register_agent(agent_server.agent_definition)

        # start agents
        for agent_server in self.agent_servers:
            asyncio.create_task(agent_server.start_processing_loop())

        # runs until the message queue is stopped by the human consumer
        await self.message_queue.start()
