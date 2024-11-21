from enum import Enum

from pydantic import BaseModel


class StatusEnum(Enum):
    HEALTHY = "Healthy"
    UNHEALTHY = "Unhealthy"
    DOWN = "Down"


class Status(BaseModel):
    status: StatusEnum
    status_message: str
    max_deployments: int | None = None
    deployments: list[str] | None = None


class DeploymentDefinition(BaseModel):
    name: str
