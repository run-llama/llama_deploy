import asyncio
import nest_asyncio

nest_asyncio.apply()
import json
import signal
import sys
import uuid
from threading import Thread, Event
from typing import Any, Callable, Dict, List, Optional

from llama_agents.services.base import BaseService
from llama_agents.control_plane.base import BaseControlPlane
from llama_agents.message_consumers.base import BaseMessageQueueConsumer
from llama_agents.message_queues.rabbitmq import RabbitMQMessageQueue
from llama_agents.message_queues.base import PublishCallback
from llama_agents.messages.base import QueueMessage
from llama_agents.types import ActionTypes, TaskDefinition, TaskResult
from llama_agents.message_publishers.publisher import MessageQueuePublisherMixin

import pika


class ConsumerThread(Thread):
    def __init__(self, consumer: BaseMessageQueueConsumer):
        super().__init__()
        self._is_interrupted = False
        self.consumer = consumer

    def stop(self):
        self._is_interrupted = True

    def run(self):
        channel = self.consumer.channel._pika_channel
        channel.queue_declare(self.consumer.message_type)
        for message in channel.consume(
            self.consumer.message_type, inactivity_timeout=1
        ):
            if self._is_interrupted:
                break
            if not all(message):
                continue
            method, properties, body = message
            payload = json.loads(body.decode("utf-8"))
            message = QueueMessage.model_validate(payload)
            asyncio.run(self.consumer.process_message(message))


class HumanMessageConsumer(BaseMessageQueueConsumer):
    message_handler: Dict[str, Callable]
    message_type: str = "human"

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        action = message.action
        if action not in self.message_handler:
            raise ValueError(f"Action {action} not supported by control plane")

        if action == ActionTypes.COMPLETED_TASK:
            await self.message_handler[action](message_data=message.data)


class LocalRabbitMQLauncher(MessageQueuePublisherMixin):
    def __init__(
        self,
        services: List[BaseService],
        control_plane: BaseControlPlane,
        message_queue: RabbitMQMessageQueue,
        publish_callback: Optional[PublishCallback] = None,
    ) -> None:
        self.services = services
        self.consumers = [s.as_consumer() for s in services] + [
            control_plane.as_consumer()
        ]
        self.additional_consumers = []
        self.control_plane = control_plane
        self._message_queue = message_queue
        self._publisher_id = f"{self.__class__.__qualname__}-{uuid.uuid4()}"
        self._publish_callback = publish_callback
        self.result: Optional[str] = None

    @property
    def message_queue(self) -> RabbitMQMessageQueue:
        return self._message_queue

    @property
    def publisher_id(self) -> str:
        return self._publisher_id

    @property
    def publish_callback(self) -> Optional[PublishCallback]:
        return self._publish_callback

    async def handle_human_message(self, **kwargs: Any) -> None:
        print(f"HANDLING HUMAN MESSAGE", flush=True)
        result = TaskResult(**kwargs["message_data"])
        print(f"result: {result.result}", flush=True)
        self.result = result

    async def register_consumers(
        self, additional_consumers: Optional[List[BaseMessageQueueConsumer]] = None
    ) -> None:
        additional_consumers = additional_consumers or []
        self.additional_consumers = additional_consumers
        for consumer in self.additional_consumers + self.consumers:
            channel = await self.message_queue.register_consumer(consumer)
            consumer.channel = channel

    def launch_single(self, initial_task: str) -> str:
        return asyncio.run(self.alaunch_single(initial_task))

    def get_shutdown_handler(self, tasks: List[asyncio.Task]) -> Callable:
        def signal_handler(sig: Any, frame: Any) -> None:
            print("\nShutting down.")
            for task in tasks:
                task.cancel()
            sys.exit(0)

        return signal_handler

    async def alaunch_single(self, initial_task: str) -> str:
        # clear any result
        self.result = None

        # register human consumer
        human_consumer = HumanMessageConsumer(
            message_handler={
                ActionTypes.COMPLETED_TASK: self.handle_human_message,
            }
        )
        await self.register_consumers([human_consumer])

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
        threads = []
        for consumer in self.additional_consumers + self.consumers:
            thread = ConsumerThread(consumer=consumer)
            thread.start()
            threads.append(thread)

        # publish initial task
        await self.publish(
            QueueMessage(
                type="control_plane",
                action=ActionTypes.NEW_TASK,
                data=TaskDefinition(input=initial_task).model_dump(),
            ),
        )

        # runs until the message queue is stopped by the human consumer
        shutdown_handler = self.get_shutdown_handler(bg_tasks)
        loop = asyncio.get_event_loop()
        while loop.is_running():
            await asyncio.sleep(0.1)
            signal.signal(signal.SIGINT, shutdown_handler)

            if self.result:
                break

        # shutdown tasks
        for task in bg_tasks:
            task.cancel()
        print(f"DONE CANCELLING TASKS", flush=True)

        # shutdown threads
        for thread in threads:
            thread.stop()
        print(f"DONE SHUTTING DOWN THREADS", flush=True)

        return self.result or "No result found."
