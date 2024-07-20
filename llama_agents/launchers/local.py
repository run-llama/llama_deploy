import asyncio
import signal
import sys
import uuid
from typing import Any, Callable, Dict, List, Optional

from llama_agents.services.base import BaseService
from llama_agents.control_plane.base import BaseControlPlane
from llama_agents.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)
from llama_agents.message_queues.simple import SimpleMessageQueue
from llama_agents.message_queues.base import BaseMessageQueue
from llama_agents.message_queues.base import PublishCallback
from llama_agents.messages.base import QueueMessage
from llama_agents.types import ActionTypes, TaskDefinition, TaskResult
from llama_agents.message_publishers.publisher import MessageQueuePublisherMixin


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
    """Launches a llama-agents system locally, in a single async loop.

    The LocalLauncher is a convenience class for launching a system of services.

    When launching, the launcher will
    - Register each service to the control plane.
    - Start each service.
    - Register a human consumer to handle messages.
    - Publish an initial task to the control plane.
    - Run until the a result is found.
    - Clean up registered services by deregistering them from the control plane.
    - Clean up consumers by deregistering them from the message queue.

    Args:
        services (List[BaseService]):
            List of services to launch.
        control_plane (BaseControlPlane):
            Control plane for the system.
        message_queue (SimpleMessageQueue):
            Message queue for the system.
        publish_callback (Optional[PublishCallback], optional):
            Callback for publishing messages. Defaults to None.

    Examples:
        ```python
        from llama_agents import LocalLauncher

        launcher = LocalLauncher(
            services=[service1, service2],
            control_plane=control_plane,
            message_queue=message_queue,
        )

        # sync
        result = launcher.launch_single("Do the thing.")

        # async
        result = await launcher.alaunch_single("Do the thing again.")
        ```
    """

    def __init__(
        self,
        services: List[BaseService],
        control_plane: BaseControlPlane,
        message_queue: BaseMessageQueue = SimpleMessageQueue(),
        publish_callback: Optional[PublishCallback] = None,
    ) -> None:
        self.services = services
        self.control_plane = control_plane
        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback
        self.result: Optional[str] = None

    @property
    def message_queue(self) -> SimpleMessageQueue:
        """Message queue."""
        return self._message_queue

    @property
    def publisher_id(self) -> str:
        """Publisher ID."""
        return self._publisher_id

    @property
    def publish_callback(self) -> Optional[PublishCallback]:
        """Publish callback, if any."""
        return self._publish_callback

    async def handle_human_message(self, **kwargs: Any) -> None:
        result = TaskResult(**kwargs["message_data"])
        self.result = result.result

    async def register_consumers(
        self, consumers: Optional[List[BaseMessageQueueConsumer]] = None
    ) -> List[StartConsumingCallable]:
        start_consuming_callables = []
        for service in self.services:
            start_consuming_callables.append(
                await self.message_queue.register_consumer(service.as_consumer())
            )

        consumers = consumers or []
        for consumer in consumers:
            start_consuming_callables.append(
                await self.message_queue.register_consumer(consumer)
            )

        start_consuming_callables.append(
            await self.message_queue.register_consumer(self.control_plane.as_consumer())
        )
        return start_consuming_callables

    def launch_single(self, initial_task: str) -> str:
        """Launch the system in a single async loop."""
        return asyncio.run(self.alaunch_single(initial_task))

    def get_shutdown_handler(self, tasks: List[asyncio.Task]) -> Callable:
        def signal_handler(sig: Any, frame: Any) -> None:
            print("\nShutting down.")
            for task in tasks:
                task.cancel()
            sys.exit(0)

        return signal_handler

    async def alaunch_single(self, initial_task: str) -> str:
        """Launch the system in a single async loop."""
        # clear any result
        self.result = None

        # register human consumer
        human_consumer = HumanMessageConsumer(
            message_handler={
                ActionTypes.COMPLETED_TASK: self.handle_human_message,
            }
        )
        start_consuming_callables = await self.register_consumers([human_consumer])

        # register each service to the control plane
        for service in self.services:
            await self.control_plane.register_service(service.service_definition)

        # start services
        bg_tasks: List[asyncio.Task] = []
        for service in self.services:
            if hasattr(service, "raise_exceptions"):
                service.raise_exceptions = True  # ensure exceptions are raised
            bg_tasks.append(await service.launch_local())

        # consumers start consuming in their own threads
        start_consuming_tasks = []
        for start_consuming_callable in start_consuming_callables:
            task = asyncio.create_task(start_consuming_callable())
            start_consuming_tasks.append(task)

        # publish initial task
        await self.publish(
            QueueMessage(
                type="control_plane",
                action=ActionTypes.NEW_TASK,
                data=TaskDefinition(input=initial_task).model_dump(),
            ),
        )
        # runs until the message queue is stopped by the human consumer
        mq_task = await self.message_queue.launch_local()
        shutdown_handler = self.get_shutdown_handler(
            [mq_task] + bg_tasks + start_consuming_tasks
        )
        loop = asyncio.get_event_loop()
        while loop.is_running():
            await asyncio.sleep(0.1)
            signal.signal(signal.SIGINT, shutdown_handler)

            for task in bg_tasks:
                if task.done() and task.exception():  # type: ignore
                    raise task.exception()  # type: ignore

            if mq_task is not None and mq_task.done() and mq_task.exception():  # type: ignore
                raise mq_task.exception()  # type: ignore

            if self.result:
                break

        # shutdown tasks
        for task in bg_tasks + start_consuming_tasks:
            task.cancel()
            await asyncio.sleep(0.1)

        # clean up registered services
        for service in self.services:
            await self.control_plane.deregister_service(
                service.service_definition.service_name
            )

        # clean up consumers
        for service in self.services:
            await self.message_queue.deregister_consumer(service.as_consumer())

        await self.message_queue.deregister_consumer(human_consumer)
        await self.message_queue.deregister_consumer(self.control_plane.as_consumer())

        # clean up before shutting down mq
        await self.message_queue.cleanup_local(
            message_types=[
                c.message_type
                for c in [s.as_consumer() for s in self.services]
                + [self.control_plane.as_consumer(), human_consumer]
            ]
        )
        mq_task.cancel()

        return self.result or "No result found."
