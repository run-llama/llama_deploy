import asyncio
import signal
import sys
import uuid
from typing import Any, Callable, List, Optional

from llama_agents.services.base import BaseService
from llama_agents.control_plane.base import BaseControlPlane
from llama_agents.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)
from llama_agents.message_queues.simple import SimpleMessageQueue
from llama_agents.message_queues.base import PublishCallback, BaseMessageQueue
from llama_agents.message_publishers.publisher import MessageQueuePublisherMixin


class ServerLauncher(MessageQueuePublisherMixin):
    """Launches a llama-agents system as a server.

    The ServerLauncher is a convenience class for launching a system of services as a server.

    When launching, the launcher will:
    - Register each service to the control plane.
    - Start each service.
    - Register any additional consumers (like handling the end of a task with a `human` consumer).
    - Run until the system is shut down.

    Args:
        services (List[BaseService]): List of services to launch.
        control_plane (BaseControlPlane): Control plane for the system.
        message_queue (SimpleMessageQueue): Message queue for the system.
        publish_callback (Optional[PublishCallback], optional): Callback for publishing messages. Defaults to None.
        additional_consumers (Optional[List[BaseMessageQueueConsumer]], optional): Additional consumers to register. Defaults to None.

    Examples:
        One script might launch the servers:
        ```python
        from llama_agents import ServerLauncher

        launcher = ServerLauncher(
            services=[service1, service2],
            control_plane=control_plane,
            message_queue=message_queue,
        )
        launcher.launch_servers()
        ```
        Another script would interact with the system using the client:
        ```python
        import time
        from llama_agents import LlamaAgentsClient

        client = LlamaAgentsClient("<control_plane_url>")

        # interact with the system
        task_id = client.create_task("Do the thing.")
        time.sleep(15) # wait for the task to complete!
        result = client.get_task_result(task_id)
        ```
    """

    def __init__(
        self,
        services: List[BaseService],
        control_plane: BaseControlPlane,
        message_queue: BaseMessageQueue,
        publish_callback: Optional[PublishCallback] = None,
        additional_consumers: Optional[List[BaseMessageQueueConsumer]] = None,
    ) -> None:
        self.services = services
        self.control_plane = control_plane
        self._message_queue = message_queue or SimpleMessageQueue()
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
        """Launch the system in multiple FastAPI servers."""
        return asyncio.run(self.alaunch_servers())

    async def alaunch_servers(self) -> None:
        """Launch the system in multiple FastAPI servers."""
        # launch the message queue
        queue_task = asyncio.create_task(self.message_queue.launch_server())

        # wait for the message queue to be ready
        await asyncio.sleep(1)

        # launch the control plane
        control_plane_task = asyncio.create_task(self.control_plane.launch_server())

        # wait for the control plane to be ready
        await asyncio.sleep(1)

        # register the control plane as a consumer
        start_consuming_callables: List[StartConsumingCallable] = []
        start_consuming_callables.append(
            await self.control_plane.register_to_message_queue()
        )

        # register the services
        control_plane_url = f"http://{self.control_plane.host}:{self.control_plane.port}"  # type: ignore
        service_tasks: List[asyncio.Task] = []
        for service in self.services:
            service_tasks.append(asyncio.create_task(service.launch_server()))
            start_consuming_callables.append(await service.register_to_message_queue())
            await service.register_to_control_plane(control_plane_url)

        # register additional consumers
        for consumer in self._additional_consumers:
            start_consuming_callables.append(
                await self.message_queue.register_consumer(consumer)
            )

        # consumers start consuming in their own threads
        start_consuming_tasks = []
        for start_consuming_callable in start_consuming_callables:
            task: asyncio.Task = asyncio.create_task(start_consuming_callable())
            start_consuming_tasks.append(task)

        shutdown_handler = self.get_shutdown_handler(
            [*service_tasks, *start_consuming_tasks, queue_task, control_plane_task]
        )
        loop = asyncio.get_event_loop()
        while loop.is_running():
            await asyncio.sleep(0.1)
            signal.signal(signal.SIGINT, shutdown_handler)

            for task in [
                *service_tasks,
                *start_consuming_tasks,
                queue_task,
                control_plane_task,
            ]:
                if task.done() and task.exception():  # type: ignore
                    raise task.exception()  # type: ignore
