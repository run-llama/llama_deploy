from typing import Any, Dict, Optional

from llama_index.core.workflow import StartEvent, StopEvent, Workflow, step
from llama_index.core.workflow.service import ServiceManager, ServiceNotFoundError

from llama_deploy.client.async_client import AsyncLlamaDeployClient
from llama_deploy.client.sync_client import LlamaDeployClient
from llama_deploy.control_plane.server import ControlPlaneConfig


class NetworkWorkflow(Workflow):
    def __init__(
        self,
        control_plane_config: ControlPlaneConfig,
        remote_service_name: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.control_plane_config = control_plane_config
        self.remote_service_name = remote_service_name

    @step
    async def run_remote_workflow(self, ev: StartEvent) -> StopEvent:
        client = AsyncLlamaDeployClient(self.control_plane_config)
        kwargs = ev.dict()

        session = await client.create_session()
        result = await session.run(self.remote_service_name, **kwargs)
        await client.delete_session(session.session_id)

        return StopEvent(result=result)


class NetworkServiceManager(ServiceManager):
    def __init__(
        self,
        control_plane_config: ControlPlaneConfig,
        existing_services: Dict[str, Workflow],
    ) -> None:
        super().__init__()
        # override with passed in/inherited services
        self._services = existing_services
        self.control_plane_config = control_plane_config

    def get(self, name: str, default: Optional["Workflow"] = None) -> "Workflow":
        try:
            local_workflow = super().get(name, default=default)
        except ServiceNotFoundError:
            local_workflow = None

        # TODO: service manager does not support async
        client = LlamaDeployClient(self.control_plane_config)
        services = client.list_services()

        remote_service = None
        for service in services:
            if service.service_name == name:
                remote_service = service
                break

        # If the remove service exists, swap it in
        if remote_service is not None:
            return NetworkWorkflow(self.control_plane_config, name, timeout=None)

        # else default to the local workflow -- if it exists
        if local_workflow is None:
            msg = f"Service {name} not found"
            raise ServiceNotFoundError(msg)

        return local_workflow
