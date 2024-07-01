import asyncio
import signal
import sys
import uuid
from typing import Any, Callable, List, Optional

from llama_agents.services.base import BaseService
from llama_agents.control_plane.base import BaseControlPlane
from llama_agents.message_consumers.base import BaseMessageQueueConsumer
from llama_agents.message_queues.simple import SimpleMessageQueue
from llama_agents.message_queues.base import PublishCallback
from llama_agents.message_publishers.publisher import MessageQueuePublisherMixin


class ServerLauncher(MessageQueuePublisherMixin):
    def __init__(
        self,
        services: List[BaseService],
        control_plane: BaseControlPlane,
        message_queue: SimpleMessageQueue,
        publish_callback: Optional[PublishCallback] = None,
        additional_consumers: Optional[List[BaseMessageQueueConsumer]] = None,
    ) -> None:
        self.services = services
        self.control_plane = control_plane
        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback
        self._additional_consumers = additional_consumers or []

    @property
    def message_queue(self) -> SimpleMessageQueue:
        return self._message_queue

    @property
    def publisher_id(self) -> str:
        return self._publisher_id

    @property
    def publish_callback(self) -> Optional[PublishCallback]:
        return self._publish_callback

    def get_shutdown_handler(self, tasks: List[asyncio.Task]) -> Callable:
        def signal_handler(sig: Any, frame: Any) -> None:
            print("\nShutting down.")
            for task in tasks:
                task.cancel()
            sys.exit(0)

        return signal_handler

    def launch_servers(self) -> None:
        return asyncio.run(self.alaunch_servers())

    async def alaunch_servers(self) -> None:
        # launch the message queue
        queue_task = asyncio.create_task(self.message_queue.launch_server())

        # wait for the message queue to be ready
        await asyncio.sleep(1)

        # launch the control plane
        control_plane_task = asyncio.create_task(self.control_plane.launch_server())

        # wait for the control plane to be ready
        await asyncio.sleep(1)

        # register the control plane as a consumer
        await self.message_queue.client.register_consumer(
            self.control_plane.as_consumer(remote=True)
        )

        # register the services
        control_plane_url = f"http://{self.control_plane.host}:{self.control_plane.port}"  # type: ignore
        service_tasks: List[asyncio.Task] = []
        for service in self.services:
            service_tasks.append(asyncio.create_task(service.launch_server()))
            await service.register_to_message_queue()
            await service.register_to_control_plane(control_plane_url)

        # register additional consumers
        for consumer in self._additional_consumers:
            await self.message_queue.register_consumer(consumer)

        shutdown_handler = self.get_shutdown_handler(
            [*service_tasks, queue_task, control_plane_task]
        )
        loop = asyncio.get_event_loop()
        while loop.is_running():
            await asyncio.sleep(0.1)
            signal.signal(signal.SIGINT, shutdown_handler)

            for task in [*service_tasks, queue_task, control_plane_task]:
                if task.done() and task.exception():  # type: ignore
                    raise task.exception()  # type: ignore
