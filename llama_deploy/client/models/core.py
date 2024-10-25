from llama_deploy.types.core import ServiceDefinition

from .model import Collection, Model


class Service(Model):
    pass


class ServiceCollection(Collection):
    async def register(self, service: ServiceDefinition) -> None:
        """Registers a service with the control plane.

        Args:
            service: Definition of the Service to register.
        """
        register_url = f"{self.client.control_plane_url}/services/register"
        await self.client.request("POST", register_url, json=service.model_dump())

    async def deregister(self, service_name: str) -> None:
        """Deregisters a service from the control plane.

        Args:
            service_name: The name of the Service to deregister.
        """
        deregister_url = f"{self.client.control_plane_url}/services/deregister"
        await self.client.request(
            "POST",
            deregister_url,
            json={"service_name": service_name},
        )


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
            items["name"] = Service.instance(client=self.client, id=name)
        return ServiceCollection.instance(client=self.client, items=items)
