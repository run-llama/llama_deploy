import asyncio
import signal
import sys

from pydantic import BaseModel
from typing import Any, Callable, List
from llama_index.core.workflow import Workflow

from llama_agents.control_plane.server import ControlPlaneConfig, ControlPlaneServer
from llama_agents.message_queues import (
    BaseMessageQueue,
    KafkaMessageQueue,
    KafkaMessageQueueConfig,
    RabbitMQMessageQueue,
    RabbitMQMessageQueueConfig,
    RedisMessageQueue,
    RedisMessageQueueConfig,
    SimpleMessageQueue,
    SimpleMessageQueueConfig,
)
from llama_agents.orchestrators.simple import SimpleOrchestrator
from llama_agents.services.workflow import WorkflowServiceConfig, WorkflowService

DEFAULT_TIMEOUT = 120.0


class Launcher:
    """Launcher client for deploying core services and workflows."""

    def _deploy_local_message_queue(
        self, config: SimpleMessageQueueConfig
    ) -> asyncio.Task:
        queue = SimpleMessageQueue(**config.model_dump())
        return asyncio.create_task(queue.launch_server())

    def _get_message_queue_client(self, config: BaseModel) -> BaseMessageQueue:
        if isinstance(config, SimpleMessageQueueConfig):
            queue = SimpleMessageQueue(**config.model_dump())
            return queue.client
        elif isinstance(config, KafkaMessageQueueConfig):
            return KafkaMessageQueue(
                **config.model_dump(),
            )
        elif isinstance(config, RabbitMQMessageQueueConfig):
            return RabbitMQMessageQueue(
                **config.model_dump(),
            )
        elif isinstance(config, RedisMessageQueueConfig):
            return RedisMessageQueue(
                **config.model_dump(),
            )
        else:
            raise ValueError(f"Invalid message queue config: {config}")

    def _get_shutdown_handler(self, tasks: List[asyncio.Task]) -> Callable:
        def signal_handler(sig: Any, frame: Any) -> None:
            print("\nShutting down.")
            for task in tasks:
                task.cancel()
            sys.exit(0)

        return signal_handler

    async def deploy_core(
        self,
        control_plane_config: ControlPlaneConfig,
        message_queue_config: BaseModel,
    ) -> None:
        message_queue_client = self._get_message_queue_client(message_queue_config)

        control_plane = ControlPlaneServer(
            message_queue_client,
            SimpleOrchestrator(),
            **control_plane_config.model_dump(),
        )

        message_queue_task = None
        if isinstance(message_queue_config, SimpleMessageQueueConfig):
            message_queue_task = self._deploy_local_message_queue(message_queue_config)

        control_plane_task = asyncio.create_task(control_plane.launch_server())

        # let services spin up
        await asyncio.sleep(1)

        # register the control plane as a consumer
        control_plane_consumer_fn = await control_plane.register_to_message_queue()

        consumer_task = asyncio.create_task(control_plane_consumer_fn())

        # let things sync up
        await asyncio.sleep(1)

        # let things run
        if message_queue_task:
            all_tasks = [control_plane_task, consumer_task, message_queue_task]
        else:
            all_tasks = [control_plane_task, consumer_task]

        shutdown_handler = self._get_shutdown_handler(all_tasks)
        loop = asyncio.get_event_loop()
        while loop.is_running():
            await asyncio.sleep(0.1)
            signal.signal(signal.SIGINT, shutdown_handler)

            for task in all_tasks:
                if task.done() and task.exception():  # type: ignore
                    raise task.exception()  # type: ignore

    async def deploy_workflow(
        self,
        workflow: Workflow,
        workflow_config: WorkflowServiceConfig,
        control_plane_config: ControlPlaneConfig,
        message_queue_config: BaseModel,
    ) -> None:
        message_queue_client = self._get_message_queue_client(message_queue_config)

        service = WorkflowService(
            workflow=workflow,
            message_queue=message_queue_client,
            **workflow_config.model_dump(),
        )

        service_task = asyncio.create_task(service.launch_server())

        # let service spin up
        await asyncio.sleep(1)

        # register to message queue
        consumer_fn = await service.register_to_message_queue()

        # register to control plane
        control_plane_url = (
            f"http://{control_plane_config.host}:{control_plane_config.port}"
        )
        await service.register_to_control_plane(control_plane_url)

        # create consumer task
        consumer_task = asyncio.create_task(consumer_fn())

        # let things sync up
        await asyncio.sleep(1)

        all_tasks = [consumer_task, service_task]

        shutdown_handler = self._get_shutdown_handler(all_tasks)
        loop = asyncio.get_event_loop()
        while loop.is_running():
            await asyncio.sleep(0.1)
            signal.signal(signal.SIGINT, shutdown_handler)

            for task in all_tasks:
                if task.done() and task.exception():  # type: ignore
                    raise task.exception()  # type: ignore
