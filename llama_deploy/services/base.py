import asyncio
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, PrivateAttr

from llama_deploy.control_plane.server import ControlPlaneConfig
from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)
from llama_deploy.message_publishers.publisher import MessageQueuePublisherMixin
from llama_deploy.messages.base import QueueMessage
from llama_deploy.types import ServiceDefinition


class BaseService(MessageQueuePublisherMixin, ABC, BaseModel):
    """Base class for a service.

    The general structure of a service is as follows:
    - A service has a name.
    - A service has a service definition.
    - A service uses a message queue to send/receive messages.
    - A service has a processing loop, for continuous processing of messages.
    - A service can process a message.
    - A service can publish a message to another service.
    - A service can be launched in-process.
    - A service can be launched as a server.
    - A service can be registered to the control plane.
    - A service can be registered to the message queue.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    model_config = ConfigDict(arbitrary_types_allowed=True)
    service_name: str
    _control_plane_url: str | None = PrivateAttr(default=None)
    _control_plane_config: ControlPlaneConfig = PrivateAttr(
        default=ControlPlaneConfig()
    )

    @property
    @abstractmethod
    def service_definition(self) -> ServiceDefinition:
        """The service definition."""
        ...

    @abstractmethod
    def as_consumer(self, remote: bool = False) -> BaseMessageQueueConsumer:
        """Get the consumer for the message queue."""
        ...

    @abstractmethod
    async def processing_loop(self) -> None:
        """The processing loop for the service."""
        ...

    @abstractmethod
    async def process_message(self, message: QueueMessage) -> Any:
        """Process a message."""
        ...

    @abstractmethod
    async def launch_local(self) -> asyncio.Task:
        """Launch the service in-process."""
        ...

    @abstractmethod
    async def launch_server(self) -> None:
        """Launch the service as a server."""
        ...

    async def register_to_control_plane(self, control_plane_url: str) -> None:
        """Register the service to the control plane."""
        self._control_plane_url = control_plane_url
        service_def = self.service_definition
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{control_plane_url}/services/register",
                json=service_def.model_dump(),
            )
            response.raise_for_status()
            self._control_plane_config = ControlPlaneConfig(**response.json())

    async def deregister_from_control_plane(self) -> None:
        """Deregister the service from the control plane."""
        if not self._control_plane_url:
            raise ValueError(
                "Control plane URL not set. Call register_to_control_plane first."
            )
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._control_plane_url}/services/deregister",
                json={"service_name": self.service_name},
            )
            response.raise_for_status()

    async def get_session_state(self, session_id: str) -> dict[str, Any] | None:
        """Get the session state from the control plane."""
        if not self._control_plane_url:
            return None

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self._control_plane_url}/sessions/{session_id}/state"
            )
            if response.status_code == 404:
                return None
            else:
                response.raise_for_status()

            return response.json()

    async def update_session_state(
        self, session_id: str, state: dict[str, Any]
    ) -> None:
        """Update the session state in the control plane."""
        if not self._control_plane_url:
            return

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._control_plane_url}/sessions/{session_id}/state",
                json=state,
            )
            response.raise_for_status()

    async def register_to_message_queue(self) -> StartConsumingCallable:
        """Register the service to the message queue."""
        return await self.message_queue.register_consumer(
            self.as_consumer(remote=True), topic=self.get_topic(self.service_name)
        )

    def get_topic(self, msg_type: str) -> str:
        return f"{self._control_plane_config.topic_namespace}.{msg_type}"
