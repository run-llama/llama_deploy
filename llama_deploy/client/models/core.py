import httpx

from llama_deploy.types.core import ServiceDefinition

from .model import Collection, Model


class Session(Model):
    pass


class SessionCollection(Collection):
    async def create(self) -> Session:
        """Creates a new session and returns a Session object.

        Returns:
            Session: A Session object representing the newly created session.
        """
        create_url = f"{self.client.control_plane_url}/sessions/create"
        response = await self.client.request("POST", create_url)
        session_id = response.json()
        return Session.instance(
            make_sync=self._instance_is_sync, client=self.client, id=session_id
        )

    async def get(self, id: str) -> Session:
        """Gets a session by ID.

        Args:
            session_id: The ID of the session to get.

        Returns:
            Session: A Session object representing the specified session.

        Raises:
            ValueError: If the session does not exist.
        """
        get_url = f"{self.client.control_plane_url}/sessions/{id}"
        await self.client.request("GET", get_url)
        return Session.instance(
            make_sync=self._instance_is_sync, client=self.client, id=id
        )

    async def get_or_create(self, id: str) -> Session:
        """Gets a session by ID, or creates a new one if it doesn't exist.

        Returns:
            Session: A Session object representing the specified session.
        """
        try:
            return await self.get(id)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return await self.create()
            raise e

    async def delete(self, session_id: str) -> None:
        """Deletes a session by ID.

        Args:
            session_id: The ID of the session to delete.
        """
        delete_url = f"{self.client.control_plane_url}/sessions/{session_id}/delete"
        await self.client.request("POST", delete_url)


class Service(Model):
    pass


class ServiceCollection(Collection):
    async def register(self, service: ServiceDefinition) -> Service:
        """Registers a service with the control plane.

        Args:
            service: Definition of the Service to register.
        """
        register_url = f"{self.client.control_plane_url}/services/register"
        await self.client.request("POST", register_url, json=service.model_dump())
        s = Service.instance(id=service.service_name, client=self.client)
        self.items[service.service_name] = s
        return s

    async def deregister(self, service_name: str) -> None:
        """Deregisters a service from the control plane.

        Args:
            service_name: The name of the Service to deregister.
        """
        deregister_url = f"{self.client.control_plane_url}/services/deregister"
        await self.client.request(
            "POST",
            deregister_url,
            params={"service_name": service_name},
        )
        self.items.pop(service_name)


class Core(Model):
    async def services(self) -> ServiceCollection:
        """Returns a collection containing all the services registered with the control plane.

        Returns:
            ServiceCollection: Collection of services registered with the control plane.
        """
        services_url = f"{self.client.control_plane_url}/services"
        response = await self.client.request("GET", services_url)
        items = {}
        for name, service in response.json().items():
            items[name] = Service.instance(
                make_sync=self._instance_is_sync, client=self.client, id=name
            )
        return ServiceCollection.instance(
            make_sync=self._instance_is_sync, client=self.client, items=items
        )

    async def sessions(self) -> SessionCollection:
        """Returns a collection containing all the sessions registered with the control plane.

        Returns:
            SessionCollection: Collection of sessions registered with the control plane.
        """
        sessions_url = f"{self.client.control_plane_url}/sessions"
        response = await self.client.request("GET", sessions_url)
        items = {}
        for id, session in response.json().items():
            items[id] = Session.instance(
                make_sync=self._instance_is_sync, client=self.client, id=id
            )
        return SessionCollection.instance(
            make_sync=self._instance_is_sync, client=self.client, items=items
        )
