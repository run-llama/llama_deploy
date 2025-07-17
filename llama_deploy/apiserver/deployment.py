import asyncio
import importlib
import json
import logging
import os
import site
import subprocess
import sys
import tempfile
from asyncio.subprocess import Process
from multiprocessing.pool import ThreadPool
from pathlib import Path
from typing import Any, Tuple, Type

from dotenv import dotenv_values
from workflows import Context, Workflow
from workflows.handler import WorkflowHandler

from llama_deploy.apiserver.source_managers.base import SyncPolicy
from llama_deploy.client import Client
from llama_deploy.types.core import generate_id

from .deployment_config_parser import (
    DeploymentConfig,
    Service,
    SourceType,
)
from .source_managers import GitSourceManager, LocalSourceManager, SourceManager
from .stats import deployment_state, service_state

logger = logging.getLogger()
SOURCE_MANAGERS: dict[SourceType, Type[SourceManager]] = {
    SourceType.git: GitSourceManager,
    SourceType.local: LocalSourceManager,
}


class DeploymentError(Exception): ...


class Deployment:
    def __init__(
        self,
        *,
        config: DeploymentConfig,
        base_path: Path,
        deployment_path: Path,
        local: bool = False,
    ) -> None:
        """Creates a Deployment instance.

        Args:
            config: The configuration object defining this deployment
            root_path: The path on the filesystem used to store deployment data
            local: Whether the deployment is local. If true, sources won't be synced
        """
        self._local = local
        self._name = config.name
        self._base_path = base_path
        # If not local, isolate the deployment in a folder with the same name to avoid conflicts
        self._deployment_path = (
            deployment_path if local else deployment_path / config.name
        )
        self._client = Client()
        self._default_service: str | None = None
        self._running = False
        self._service_tasks: list[asyncio.Task] = []
        self._ui_server_process: Process | None = None
        # Ready to load services
        self._workflow_services: dict[str, Workflow] = self._load_services(config)
        self._contexts: dict[str, Context] = {}
        self._handlers: dict[str, WorkflowHandler] = {}
        self._handler_inputs: dict[str, str] = {}
        self._config = config
        deployment_state.labels(self._name).state("ready")

    @property
    def default_service(self) -> str:
        if not self._default_service:
            self._default_service = list(self._workflow_services.keys())[0]
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
    def service_names(self) -> list[str]:
        """Returns the list of service names in this deployment."""
        return list(self._workflow_services.keys())

    async def run_workflow(
        self, service_id: str, session_id: str | None = None, **run_kwargs: dict
    ) -> Any:
        workflow = self._workflow_services[service_id]
        if session_id:
            context = self._contexts[session_id]
            return await workflow.run(context=context, **run_kwargs)

        if run_kwargs:
            return await workflow.run(**run_kwargs)

        return await workflow.run()

    def run_workflow_no_wait(
        self, service_id: str, session_id: str | None = None, **run_kwargs: dict
    ) -> Tuple[str, str]:
        workflow = self._workflow_services[service_id]
        if session_id:
            context = self._contexts[session_id]
            handler = workflow.run(context=context, **run_kwargs)
        else:
            handler = workflow.run(**run_kwargs)
            session_id = generate_id()
            self._contexts[session_id] = handler.ctx or Context(workflow)

        handler_id = generate_id()
        self._handlers[handler_id] = handler
        self._handler_inputs[handler_id] = json.dumps(run_kwargs)
        return handler_id, session_id

    async def start(self) -> None:
        """The task that will be launched in this deployment asyncio loop.

        This task is responsible for launching asyncio tasks for the core components and the services.
        All the tasks are gathered before returning.
        """
        self._running = True

        # UI
        if self._config.ui:
            await self._start_ui_server()

    async def reload(self, config: DeploymentConfig) -> None:
        # Reset default service, it might change across reloads
        self._default_service = None
        # Tear down the UI server
        self._stop_ui_server()
        # Reload the services
        self._workflow_services = self._load_services(config)

        # UI
        if self._config.ui:
            await self._start_ui_server()

    def _stop_ui_server(self) -> None:
        if self._ui_server_process is None:
            return

        self._ui_server_process.terminate()

    async def _start_ui_server(self) -> None:
        """Creates WorkflowService instances according to the configuration object."""
        if not self._config.ui:
            raise ValueError("missing ui configuration settings")

        source = self._config.ui.source
        if source is None:
            raise ValueError("source must be defined")

        # Sync the service source
        destination = self._deployment_path.resolve()
        source_manager = SOURCE_MANAGERS[source.type](self._config, self._base_path)
        policy = source.sync_policy or (
            SyncPolicy.SKIP if self._local else SyncPolicy.REPLACE
        )
        source_manager.sync(source.location, str(destination), policy)
        installed_path = destination / source_manager.relative_path(source.location)

        install = await asyncio.create_subprocess_exec(
            "pnpm", "install", cwd=installed_path
        )
        await install.wait()

        env = os.environ.copy()
        env["LLAMA_DEPLOY_NEXTJS_BASE_PATH"] = f"/deployments/{self._config.name}/ui"
        env["LLAMA_DEPLOY_NEXTJS_DEPLOYMENT_NAME"] = self._config.name
        # Override PORT and force using the one from the deployment.yaml file
        env["PORT"] = str(self._config.ui.port)

        self._ui_server_process = await asyncio.create_subprocess_exec(
            "pnpm",
            "run",
            "dev",
            cwd=installed_path,
            env=env,
        )

        print(f"Started Next.js app with PID {self._ui_server_process.pid}")

    def _load_services(self, config: DeploymentConfig) -> dict[str, Workflow]:
        """Creates WorkflowService instances according to the configuration object."""
        deployment_state.labels(self._name).state("loading_services")
        workflow_services = {}
        for service_id, service_config in config.services.items():
            service_state.labels(self._name, service_id).state("loading")
            source = service_config.source
            if source is None:
                # this is a default service, skip for now
                # TODO: check the service name is valid and supported
                # TODO: possibly start the default service if not running already
                continue

            if service_config.import_path is None:
                msg = "path field in service definition must be set"
                raise ValueError(msg)

            # Sync the service source
            service_state.labels(self._name, service_id).state("syncing")
            destination = self._deployment_path.resolve()
            source_manager = SOURCE_MANAGERS[source.type](config, self._base_path)
            policy = SyncPolicy.SKIP if self._local else SyncPolicy.REPLACE
            source_manager.sync(source.location, str(destination), policy)

            # Install dependencies
            service_state.labels(self._name, service_id).state("installing")
            self._install_dependencies(service_config, destination)

            # Set environment variables
            self._set_environment_variables(service_config, destination)

            # Search for a workflow instance in the service path
            module_path_str, workflow_name = service_config.import_path.split(":")
            module_path = Path(module_path_str)
            module_name = module_path.name
            pythonpath = (destination / module_path.parent).resolve()
            logger.debug("Extending PYTHONPATH to %s", pythonpath)
            sys.path.append(str(pythonpath))

            module = importlib.import_module(module_name)
            workflow_services[service_id] = getattr(module, workflow_name)

            service_state.labels(self._name, service_id).state("ready")

        if config.default_service:
            if config.default_service in workflow_services:
                self._default_service = config.default_service
            else:
                msg = f"Service with id '{config.default_service}' does not exist, cannot set it as default."
                logger.warning(msg)
                self._default_service = None

        return workflow_services

    @staticmethod
    def _validate_path_is_safe(
        path: str, source_root: Path, path_type: str = "path"
    ) -> None:
        """Validates that a path is within the source root to prevent path traversal attacks.

        Args:
            path: The path to validate
            source_root: The root directory that paths should be relative to
            path_type: Description of the path type for error messages

        Raises:
            DeploymentError: If the path is outside the source root
        """
        resolved_path = (source_root / path).resolve()
        resolved_source_root = source_root.resolve()

        if not resolved_path.is_relative_to(resolved_source_root):
            msg = f"{path_type} {path} is not a subdirectory of the source root {source_root}"
            raise DeploymentError(msg)

    @staticmethod
    def _set_environment_variables(
        service_config: Service, root: Path | None = None
    ) -> None:
        """Sets environment variables for the service."""
        env_vars: dict[str, str | None] = {}

        if service_config.env:
            env_vars.update(**service_config.env)

        if service_config.env_files:
            for env_file in service_config.env_files:
                # use dotenv to parse env_file
                env_file_path = root / env_file if root else Path(env_file)
                env_vars.update(**dotenv_values(env_file_path))

        for k, v in env_vars.items():
            if v:
                os.environ[k] = v

    @staticmethod
    def _install_dependencies(service_config: Service, source_root: Path) -> None:
        """Runs `pip install` on the items listed under `python-dependencies` in the service configuration."""
        if not service_config.python_dependencies:
            return
        install_args = []
        for dep in service_config.python_dependencies or []:
            if dep.endswith("requirements.txt"):
                Deployment._validate_path_is_safe(dep, source_root, "requirements file")
                resolved_dep = source_root / dep
                install_args.extend(["-r", str(resolved_dep)])
            else:
                if "." in dep or "/" in dep:
                    Deployment._validate_path_is_safe(
                        dep, source_root, "dependency path"
                    )
                    resolved_dep = source_root / dep
                    if os.path.isfile(resolved_dep) or os.path.isdir(resolved_dep):
                        # install as editable, such that sources are left in place, and can reference repository files
                        install_args.extend(["-e", str(resolved_dep.resolve())])
                    else:
                        install_args.append(dep)
                else:
                    install_args.append(dep)

        # Check if uv is available on the path
        uv_available = False
        try:
            subprocess.check_call(
                ["uv", "--version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            uv_available = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        if not uv_available:
            # bootstrap uv with pip
            try:
                subprocess.check_call(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "uv",
                    ]
                )
            except subprocess.CalledProcessError as e:
                msg = f"Unable to install uv. Environment must include uv, or uv must be installed with pip: {e.stderr}"
                raise DeploymentError(msg)

        # Bit of an ugly hack, install to whatever python environment we're currently in
        # Find the python bin path and get its parent dir, and install into whatever that
        # python is. Hopefully we're in a container or a venv, otherwise this is installing to
        # the system python
        # https://docs.astral.sh/uv/concepts/projects/config/#project-environment-path
        python_bin_path = os.path.dirname(sys.executable)
        python_parent_dir = os.path.dirname(python_bin_path)
        if install_args:
            try:
                subprocess.check_call(
                    [
                        "uv",
                        "pip",
                        "install",
                        f"--prefix={python_parent_dir}",  # installs to the current python environment
                        *install_args,
                    ],
                    cwd=source_root,
                )

                # Force Python to refresh its package discovery after installing new packages
                site.main()  # Refresh site-packages paths
                # Clear import caches to ensure newly installed packages are discoverable
                importlib.invalidate_caches()

            except subprocess.CalledProcessError as e:
                msg = f"Unable to install service dependencies using command '{e.cmd}': {e.stderr}"
                raise DeploymentError(msg) from None


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

    def __init__(self, max_deployments: int = 10) -> None:
        """Creates a Manager instance.

        Args:
            max_deployments: The maximum number of deployments supported by this manager.
        """
        self._deployments: dict[str, Deployment] = {}
        self._deployments_path: Path | None = None
        self._max_deployments = max_deployments
        self._pool = ThreadPool(processes=max_deployments)
        self._last_control_plane_port = 8002
        self._simple_message_queue_server: asyncio.Task | None = None
        self._serving = False

    @property
    def deployment_names(self) -> list[str]:
        """Return a list of names for the active deployments."""
        return list(self._deployments.keys())

    @property
    def deployments_path(self) -> Path:
        if self._deployments_path is None:
            raise ValueError("Deployments path not set")
        return self._deployments_path

    def set_deployments_path(self, path: Path | None) -> None:
        self._deployments_path = (
            path or Path(tempfile.gettempdir()) / "llama_deploy" / "deployments"
        )

    def get_deployment(self, deployment_name: str) -> Deployment | None:
        return self._deployments.get(deployment_name)

    async def serve(self) -> None:
        """The server loop, it keeps the manager running."""
        if self._deployments_path is None:
            raise RuntimeError("Deployments path not set")

        self._serving = True

        event = asyncio.Event()
        try:
            # Waits indefinitely since `event` will never be set
            await event.wait()
        except asyncio.CancelledError:
            if self._simple_message_queue_server is not None:
                self._simple_message_queue_server.cancel()
                await self._simple_message_queue_server

    async def deploy(
        self,
        config: DeploymentConfig,
        base_path: str,
        reload: bool = False,
        local: bool = False,
    ) -> None:
        """Creates a Deployment instance and starts the relative runtime.

        Args:
            config: The deployment configuration.
            reload: Reload an existing deployment instead of raising an error.
            local: Deploy a local configuration. Source code will be used in place locally.

        Raises:
            ValueError: If a deployment with the same name already exists or the maximum number of deployment exceeded.
            DeploymentError: If it wasn't possible to create a deployment.
        """
        if not self._serving:
            raise RuntimeError("Manager main loop not started, call serve() first.")

        if not reload:
            # Raise an error if deployment already exists
            if config.name in self._deployments:
                msg = f"Deployment already exists: {config.name}"
                raise ValueError(msg)

            # Raise an error if we can't create any new deployment
            if len(self._deployments) == self._max_deployments:
                msg = "Reached the maximum number of deployments, cannot schedule more"
                raise ValueError(msg)

            deployment = Deployment(
                config=config,
                base_path=Path(base_path),
                deployment_path=self.deployments_path,
                local=local,
            )
            self._deployments[config.name] = deployment
            await deployment.start()
        else:
            if config.name not in self._deployments:
                msg = f"Cannot find deployment to reload: {config.name}"
                raise ValueError(msg)

            deployment = self._deployments[config.name]
            await deployment.reload(config)
