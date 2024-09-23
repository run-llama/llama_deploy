import asyncio
import importlib
import sys
from multiprocessing.pool import ThreadPool
from pathlib import Path
from typing import Any

from llama_deploy import (
    ControlPlaneServer,
    SimpleMessageQueue,
    SimpleOrchestratorConfig,
    SimpleOrchestrator,
    WorkflowService,
    WorkflowServiceConfig,
)
from llama_deploy.message_queues import (
    BaseMessageQueue,
    SimpleMessageQueueConfig,
    AWSMessageQueue,
    KafkaMessageQueue,
    RabbitMQMessageQueue,
    RedisMessageQueue,
)

from .config_parser import (
    Config,
    SourceType,
    MessageQueueConfigSimple,
    MessageQueueConfig,
)
from .source_managers import GitSourceManager


SOURCE_MANAGERS = {SourceType.git: GitSourceManager()}


class Deployment:
    """A Deployment consists of running services and core component instances.

    Every Deployment is self contained, running a dedicated instance of the control plane
    and the message queue along with any service defined in the configuration object.
    """

    def __init__(self, *, config: Config, root_path: Path) -> None:
        """Creates a Deployment instance.

        Args:
            config: The configuration object defining this deployment
            root_path: The path on the filesystem used to store deployment data
        """
        self._name = config.name
        self._path = root_path / config.name
        self._queue = SimpleMessageQueue(**SimpleMessageQueueConfig().model_dump())
        self._control_plane = ControlPlaneServer(
            self._queue,
            SimpleOrchestrator(**SimpleOrchestratorConfig().model_dump()),
            **config.control_plane.model_dump(),
        )
        self._workflow_services: list[WorkflowService] = self._load_services(config)

    @property
    def name(self) -> str:
        """Returns the name of this deployment."""
        return self._name

    @property
    def path(self) -> Path:
        """Returns the absolute path to the root of this deployment."""
        return self._path.resolve()

    async def start(self) -> None:
        """The task that will be launched in this deployment asyncio loop.

        This task is responsible for launching asyncio tasks for the core components and the services.
        All the tasks are gathered before returning.
        """
        tasks = []

        # Spawn SimpleMessageQueue if needed
        if self._simple_message_queue_task:
            # If SimpleMessageQueue was selected in the config file we take care of running the task
            tasks.append(asyncio.create_task(self._queue.launch_server()))
            # the other components need the queue to run in order to start, give the queue some time to start
            # FIXME: having to await a magic number of seconds is very brittle, we should rethink the bootstrap process
            await asyncio.sleep(1)

        # Control Plane
        cp_consumer_fn = await self._control_plane.register_to_message_queue()
        tasks.append(asyncio.create_task(self._control_plane.launch_server()))
        tasks.append(asyncio.create_task(cp_consumer_fn()))

        # Services
        for wfs in self._workflow_services:
            service_task = asyncio.create_task(wfs.launch_server())
            tasks.append(service_task)
            consumer_fn = await wfs.register_to_message_queue()
            control_plane_url = (
                f"http://{self._control_plane.host}:{self._control_plane.port}"
            )
            await wfs.register_to_control_plane(control_plane_url)
            consumer_task = asyncio.create_task(consumer_fn())
            tasks.append(consumer_task)

        # Run allthethings
        await asyncio.gather(*tasks)

    def _load_services(self, config: Config) -> list[WorkflowService]:
        """Creates WorkflowService instances according to the configuration object."""
        workflow_services = []
        for service_id, service_config in config.services.items():
            source = service_config.source
            if source is None:
                # this is a default service, skip for now
                # TODO: check the service name is valid and supported
                # TODO: possibly start the default service if not running already
                continue

            # FIXME: Momentarily assuming everything is a workflow
            if service_config.path is None:
                msg = "path field in service definition must be set"
                raise ValueError(msg)

            # Sync the service source
            destination = self._path / service_id
            source_manager = SOURCE_MANAGERS[source.type]
            source_manager.sync(source.name, str(destination.resolve()))

            # Search for a workflow instance in the service path
            pythonpath = (destination / service_config.path).parent.resolve()
            sys.path.append(str(pythonpath))
            module_name, workflow_name = Path(service_config.path).name.split(":")
            module = importlib.import_module(module_name)
            workflow = getattr(module, workflow_name)
            workflow_config = WorkflowServiceConfig(
                host="workflow",
                port=8002,
                internal_host="0.0.0.0",
                internal_port=8002,
                service_name=workflow_name,
            )
            workflow_services.append(
                WorkflowService(
                    workflow=workflow,
                    message_queue=self._queue,
                    **workflow_config.model_dump(),
                )
            )

        return workflow_services

    def _load_message_queue(self, cfg: MessageQueueConfig | None) -> BaseMessageQueue:
        # Use the SimpleMessageQueue as the default
        if cfg is None:
            # we use model_validate instead of __init__ to avoid static checkers complaining over field aliases
            cfg = MessageQueueConfigSimple.model_validate(
                {
                    "queue-type": "simple",
                    "config": SimpleMessageQueueConfig(),
                }
            )

        if cfg.queue_type == "aws":
            return AWSMessageQueue(**cfg.model_dump())
        elif cfg.queue_type == "kafka":
            return KafkaMessageQueue(**cfg.model_dump())
        elif cfg.queue_type == "rabbitmq":
            return RabbitMQMessageQueue(**cfg.model_dump())
        elif cfg.queue_type == "redis":
            return RedisMessageQueue(**cfg.model_dump())
        elif cfg.queue_type == "simple":
            self._simple_message_queue_task = SimpleMessageQueue(
                **cfg.config.model_dump()
            )
            return self._simple_message_queue_task.client
        else:
            msg = f"Unsupported message queue: {cfg.queue_type}"
            raise ValueError(msg)


class Manager:
    """The Manager orchestrates deployments and their runtime.

    Usage example:
        ```python
        config = Config.from_yaml(data_path / "git_service.yaml")
        manager = Manager(tmp_path)
        t = threading.Thread(target=asyncio.run, args=(manager.serve(),))
        t.start()
        manager.deploy(config)
        t.join()
        ```
    """

    def __init__(
        self, deployments_path: Path = Path(".deployments"), max_deployments: int = 10
    ) -> None:
        """Creates a Manager instance.

        Args:
            deployments_path: The filesystem path where deployments will create their root path.
            max_deployments: The maximum number of deployments supported by this manager.
        """
        self._deployments: dict[str, Any] = {}
        self._deployments_path = deployments_path
        self._max_deployments = max_deployments
        self._pool = ThreadPool(processes=max_deployments)

    async def serve(self) -> None:
        """The server loop, it keeps the manager running."""
        event = asyncio.Event()
        try:
            # Waits indefinitely since `event` will never be set
            await event.wait()
        except asyncio.CancelledError:
            pass

    def deploy(self, config: Config) -> None:
        """Creates a Deployment instance and starts the relative runtime.

        Args:
            config: The deployment configuration.

        Raises:
            ValueError: If a deployment with the same name already exists
        """
        if config.name in self._deployments:
            msg = f"Deployment already exists: {config.name}"
            raise ValueError(msg)

        if len(self._deployments) == self._max_deployments:
            msg = "Reached the maximum number of deployments, cannot schedule more"
            raise ValueError(msg)

        deployment = Deployment(config=config, root_path=self._deployments_path)
        self._deployments[config.name] = deployment
        self._pool.apply_async(func=asyncio.run, args=(deployment.start(),))
