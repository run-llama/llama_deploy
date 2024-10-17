from enum import StrEnum

from pydantic import BaseModel

from .model import Model


class ApiServerStatusEnum(StrEnum):
    HEALTHY = "Healthy"
    UNHEALTHY = "Unhealthy"
    DOWN = "Down"


class ApiServerStatus(BaseModel):
    status: ApiServerStatusEnum
    description: str


class ApiServer(Model):
    async def status(self) -> ApiServerStatus:
        """Returns the status of the API Server."""
        settings = self.client.settings
        status_url = f"{settings.api_server_url}/status/"

        r = await self.client.request(
            "GET", status_url, verify=not settings.disable_ssl, timeout=settings.timeout
        )

        if r is None:
            return ApiServerStatus(
                status=ApiServerStatusEnum.DOWN, description="API Server is down"
            )

        if r.status_code >= 400:
            body = r.json()
            return ApiServerStatus(
                status=ApiServerStatusEnum.UNHEALTHY, description=r.text
            )

        description = "Llama Deploy is up and running."
        body = r.json()
        if deployments := body.get("deployments"):
            description += "\nActive deployments:"
            for d in deployments:
                description += f"- {d}"
        else:
            description += "\nCurrently there are no active deployments"

        return ApiServerStatus(
            status=ApiServerStatusEnum.HEALTHY, description=description
        )
