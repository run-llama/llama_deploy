import asyncio
import httpx
import signal
import sys

from llama_deploy.message_queues.simple import SimpleRemoteClientMessageQueue
from pydantic_settings import BaseSettings
from typing import Any, Callable, List, Optional
from llama_index.core.workflow import Workflow

from llama_deploy.control_plane.server import ControlPlaneConfig, ControlPlaneServer
from llama_deploy.deploy.network_workflow import NetworkServiceManager
from llama_deploy.message_queues import (
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
from llama_deploy.orchestrators.simple import (
    SimpleOrchestrator,
    SimpleOrchestratorConfig,
)
from llama_deploy.services.workflow import WorkflowServiceConfig, WorkflowService

DEFAULT_TIMEOUT = 120.0


def _deploy_local_message_queue(config: SimpleMessageQueueConfig) -> asyncio.Task:
    queue = SimpleMessageQueue(**config.model_dump())
    return asyncio.create_task(queue.launch_server())


def _get_message_queue_config(config_dict: dict) -> BaseSettings:
    key = next(iter(config_dict.keys()))
    if key == SimpleMessageQueueConfig.__name__:
        return SimpleMessageQueueConfig(**config_dict[key])
    elif key == SimpleRemoteClientMessageQueue.__name__:
        return SimpleMessageQueueConfig(**config_dict[key])
    elif key == KafkaMessageQueueConfig.__name__:
        return KafkaMessageQueueConfig(**config_dict[key])
    elif key == RabbitMQMessageQueueConfig.__name__:
        return RabbitMQMessageQueueConfig(**config_dict[key])
    elif key == RedisMessageQueueConfig.__name__:
        return RedisMessageQueueConfig(**config_dict[key])
    else:
        raise ValueError(f"Unknown message queue: {key}")


def _get_message_queue_client(config: BaseSettings) -> BaseMessageQueue:
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


def _get_shutdown_handler(tasks: List[asyncio.Task]) -> Callable:
    def signal_handler(sig: Any, frame: Any) -> None:
        print("\nShutting down.")
        for task in tasks:
            task.cancel()
        sys.exit(0)

    return signal_handler


async def deploy_core(
    control_plane_config: Optional[ControlPlaneConfig] = None,
    message_queue_config: Optional[BaseSettings] = None,
    orchestrator_config: Optional[SimpleOrchestratorConfig] = None,
    disable_message_queue: bool = False,
    disable_control_plane: bool = False,
) -> None:
    """
    Deploy the core components of the llama_deploy system.

    This function sets up and launches the message queue, control plane, and orchestrator.
    It handles the initialization and connection of these core components.

    Args:
        control_plane_config (Optional[ControlPlaneConfig]): Configuration for the control plane.
        message_queue_config (Optional[BaseSettings]): Configuration for the message queue. Defaults to a local SimpleMessageQueue.
        orchestrator_config (Optional[SimpleOrchestratorConfig]): Configuration for the orchestrator.
            If not provided, a default SimpleOrchestratorConfig will be used.
        disable_message_queue (bool): Whether to disable deploying the message queue. Defaults to False.
        disable_control_plane (bool): Whether to disable deploying the control plane. Defaults to False.

    Raises:
        ValueError: If an unknown message queue type is specified in the config.
        Exception: If any of the launched tasks encounter an error.
    """
    control_plane_config = control_plane_config or ControlPlaneConfig()
    message_queue_config = message_queue_config or SimpleMessageQueueConfig()
    orchestrator_config = orchestrator_config or SimpleOrchestratorConfig()

    message_queue_client = _get_message_queue_client(message_queue_config)

    control_plane = ControlPlaneServer(
        message_queue_client,
        SimpleOrchestrator(**orchestrator_config.model_dump()),
        **control_plane_config.model_dump(),
    )

    if (
        isinstance(message_queue_config, SimpleMessageQueueConfig)
        and not disable_message_queue
    ):
        message_queue_task = _deploy_local_message_queue(message_queue_config)
    elif (
        isinstance(message_queue_config, SimpleMessageQueueConfig)
        and disable_message_queue
    ):
        # create a dummy task to keep the event loop running
        message_queue_task = asyncio.create_task(asyncio.sleep(0))
    else:
        message_queue_task = asyncio.create_task(asyncio.sleep(0))

    if not disable_control_plane:
        control_plane_task = asyncio.create_task(control_plane.launch_server())

        # let services spin up
        await asyncio.sleep(1)

        # register the control plane as a consumer
        control_plane_consumer_fn = await control_plane.register_to_message_queue()

        consumer_task = asyncio.create_task(control_plane_consumer_fn())
    else:
        # create a dummy task to keep the event loop running
        control_plane_task = asyncio.create_task(asyncio.sleep(0))
        consumer_task = asyncio.create_task(asyncio.sleep(0))

    # let things sync up
    await asyncio.sleep(1)

    # let things run
    all_tasks = [control_plane_task, consumer_task, message_queue_task]

    shutdown_handler = _get_shutdown_handler(all_tasks)
    loop = asyncio.get_event_loop()
    while loop.is_running():
        await asyncio.sleep(0.1)
        signal.signal(signal.SIGINT, shutdown_handler)

        for task in all_tasks:
            if task.done() and task.exception():  # type: ignore
                raise task.exception()  # type: ignore


async def deploy_workflow(
    workflow: Workflow,
    workflow_config: WorkflowServiceConfig,
    control_plane_config: Optional[ControlPlaneConfig] = None,
) -> None:
    """
    Deploy a workflow as a service within the llama_deploy system.

    This function sets up a workflow as a service, connects it to the message queue,
    and registers it with the control plane.

    Args:
        workflow (Workflow): The workflow to be deployed as a service.
        workflow_config (WorkflowServiceConfig): Configuration for the workflow service.
        control_plane_config (Optional[ControlPlaneConfig]): Configuration for the control plane.

    Raises:
        httpx.HTTPError: If there's an error communicating with the control plane.
        ValueError: If an invalid message queue config is encountered.
        Exception: If any of the launched tasks encounter an error.
    """
    control_plane_config = control_plane_config or ControlPlaneConfig()
    control_plane_url = control_plane_config.url

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{control_plane_url}/queue_config")
        queue_config_dict = response.json()

    message_queue_config = _get_message_queue_config(queue_config_dict)
    message_queue_client = _get_message_queue_client(message_queue_config)

    # override the service manager, while maintaining dict of existing services
    workflow._service_manager = NetworkServiceManager(
        control_plane_config, workflow._service_manager._services
    )

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

    shutdown_handler = _get_shutdown_handler(all_tasks)
    loop = asyncio.get_event_loop()
    while loop.is_running():
        await asyncio.sleep(0.1)
        signal.signal(signal.SIGINT, shutdown_handler)

        for task in all_tasks:
            if task.done() and task.exception():  # type: ignore
                raise task.exception()  # type: ignore
