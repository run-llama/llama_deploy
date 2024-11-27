import asyncio
import importlib
import subprocess
import sys
from multiprocessing.pool import ThreadPool
from pathlib import Path
from typing import Any

from llama_deploy import (
    Client,
    ControlPlaneServer,
    SimpleMessageQueue,
    SimpleOrchestrator,
    SimpleOrchestratorConfig,
    WorkflowService,
    WorkflowServiceConfig,
)
from llama_deploy.message_queues import (
    AWSMessageQueue,
    BaseMessageQueue,
    KafkaMessageQueue,
    RabbitMQMessageQueue,
    RedisMessageQueue,
    SimpleMessageQueueConfig,
    SolaceMessageQueue,
)

from .config_parser import Config, MessageQueueConfig, Service, SourceType
from .source_managers import GitSourceManager, LocalSourceManager, SourceManager

SOURCE_MANAGERS: dict[SourceType, SourceManager] = {
    SourceType.git: GitSourceManager(),
    SourceType.local: LocalSourceManager(),
}


class DeploymentError(Exception): ...


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
        self._simple_message_queue: SimpleMessageQueue | None = None
        self._queue_client = self._load_message_queue_client(config.message_queue)
        self._control_plane_config = config.control_plane
        self._control_plane = ControlPlaneServer(
            self._queue_client,
            SimpleOrchestrator(**SimpleOrchestratorConfig().model_dump()),
            config=config.control_plane,
        )
        self._workflow_services: list[WorkflowService] = self._load_services(config)
        self._client = Client(control_plane_url=config.control_plane.url)
        self._default_service = config.default_service

    @property
    def default_service(self) -> str | None:
        return self._default_service

    @property
    def client(self) -> Client:
        """Returns an async client to interact with this deployment."""
        return self._client

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
        if self._simple_message_queue:
            # If SimpleMessageQueue was selected in the config file we take care of running the task
            tasks.append(
                asyncio.create_task(self._simple_message_queue.launch_server())
            )
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
            control_plane_url = f"http://{self._control_plane_config.host}:{self._control_plane_config.port}"
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

            if service_config.port is None:
                # This won't happen if we arrive here from Manager.deploy(), the manager will assign a port
                msg = "port field in service definition must be set"
                raise ValueError(msg)

            if service_config.host is None:
                # This won't happen if we arrive here from Manager.deploy(), the manager will assign a host
                msg = "host field in service definition must be set"
                raise ValueError(msg)

            # Sync the service source
            destination = self._path / service_id
            source_manager = SOURCE_MANAGERS[source.type]
            source_manager.sync(source.name, str(destination.resolve()))

            # Install dependencies
            self._install_dependencies(service_config)

            # Search for a workflow instance in the service path
            pythonpath = (destination / service_config.path).parent.resolve()
            sys.path.append(str(pythonpath))
            module_name, workflow_name = Path(service_config.path).name.split(":")
            module = importlib.import_module(module_name)
            workflow = getattr(module, workflow_name)
            workflow_config = WorkflowServiceConfig(
                host=service_config.host,
                port=service_config.port,
                internal_host="0.0.0.0",
                internal_port=service_config.port,
                service_name=service_id,
            )
            workflow_services.append(
                WorkflowService(
                    workflow=workflow,
                    message_queue=self._queue_client,
                    **workflow_config.model_dump(),
                )
            )

        return workflow_services

    @staticmethod
    def _install_dependencies(service_config: Service) -> None:
        """Runs `pip install` on the items listed under `python-dependencies` in the service configuration."""
        if not service_config.python_dependencies:
            return

        try:
            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    *service_config.python_dependencies,
                ]
            )
        except subprocess.CalledProcessError as e:
            msg = f"Unable to install service dependencies using command '{e.cmd}': {e.stderr}"
            raise DeploymentError(msg) from None

    def _load_message_queue_client(
        self, cfg: MessageQueueConfig | None
    ) -> BaseMessageQueue:
        # Use the SimpleMessageQueue as the default
        if cfg is None:
            # we use model_validate instead of __init__ to avoid static checkers complaining over field aliases
            cfg = SimpleMessageQueueConfig()

        if cfg.type == "aws":
            return AWSMessageQueue(**cfg.model_dump())
        elif cfg.type == "kafka":
            return KafkaMessageQueue(cfg)  # type: ignore
        elif cfg.type == "rabbitmq":
            return RabbitMQMessageQueue(cfg)  # type: ignore
        elif cfg.type == "redis":
            return RedisMessageQueue(**cfg.model_dump())
        elif cfg.type == "simple":
            self._simple_message_queue = SimpleMessageQueue(**cfg.model_dump())
            return self._simple_message_queue.client
        elif cfg.type == "solace":
            return SolaceMessageQueue(**cfg.model_dump())
        else:
            msg = f"Unsupported message queue: {cfg.type}"
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
        self._control_plane_port = 8002

    @property
    def deployment_names(self) -> list[str]:
        """Return a list of names for the active deployments."""
        return list(self._deployments.keys())

    def get_deployment(self, deployment_name: str) -> Deployment | None:
        return self._deployments.get(deployment_name)

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
            ValueError: If a deployment with the same name already exists or the maximum number of deployment exceeded.
            DeploymentError: If it wasn't possible to create a deployment.
        """
        if config.name in self._deployments:
            msg = f"Deployment already exists: {config.name}"
            raise ValueError(msg)

        if len(self._deployments) == self._max_deployments:
            msg = "Reached the maximum number of deployments, cannot schedule more"
            raise ValueError(msg)

        self._assign_control_plane_address(config)

        deployment = Deployment(config=config, root_path=self._deployments_path)
        self._deployments[config.name] = deployment
        self._pool.apply_async(func=asyncio.run, args=(deployment.start(),))

    def _assign_control_plane_address(self, config: Config) -> None:
        for service in config.services.values():
            if not service.port:
                service.port = self._control_plane_port
                self._control_plane_port += 1
            if not service.host:
                service.host = "localhost"
