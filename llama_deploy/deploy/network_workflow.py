import warnings
from typing import Any, Dict, Optional

from llama_index.core.workflow import StartEvent, StopEvent, Workflow, step
from llama_index.core.workflow.service import ServiceManager, ServiceNotFoundError

from llama_deploy.client import Client
from llama_deploy.control_plane.server import ControlPlaneConfig


class NetworkWorkflow(Workflow):
    def __init__(
        self,
        remote_service_name: str,
        control_plane_config: ControlPlaneConfig | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if control_plane_config is not None:
            warnings.warn(
                "The control_plane_config parameter is deprecated and will be removed in a future version.",
                DeprecationWarning,
                stacklevel=2,
            )
        self.remote_service_name = remote_service_name
        # Use the same timeout for the client
        self._client = Client(timeout=self._timeout)

    @step
    async def run_remote_workflow(self, ev: StartEvent) -> StopEvent:
        session = await self._client.core.sessions.create()
        result = await session.run(self.remote_service_name, **ev.dict())
        await self._client.core.sessions.delete(session.id)

        return StopEvent(result=result)


class NetworkServiceManager(ServiceManager):
    def __init__(
        self,
        existing_services: Dict[str, Workflow] | None = None,
        control_plane_config: ControlPlaneConfig | None = None,
    ) -> None:
        super().__init__()
        if control_plane_config is not None:
            warnings.warn(
                "The control_plane_config parameter is deprecated and will be removed in a future version.",
                DeprecationWarning,
                stacklevel=2,
            )
        # override with passed in/inherited services
        self._services: Dict[str, Workflow] = existing_services or {}
        self._client = Client()

    def get(self, name: str, default: Optional["Workflow"] = None) -> "Workflow":
        try:
            local_workflow = super().get(name, default=default)
        except ServiceNotFoundError:
            local_workflow = None

        services = self._client.sync.core.services.list()

        remote_service = None
        for service in services:
            if service.service_name == name:
                remote_service = service
                break

        # If the remove service exists, swap it in
        if remote_service is not None:
            return NetworkWorkflow(name, timeout=None)

        # else default to the local workflow -- if it exists
        if local_workflow is None:
            msg = f"Service {name} not found"
            raise ServiceNotFoundError(msg)

        return local_workflow
