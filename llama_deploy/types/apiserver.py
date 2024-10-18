from enum import StrEnum

from pydantic import BaseModel


class StatusEnum(StrEnum):
    HEALTHY = "Healthy"
    UNHEALTHY = "Unhealthy"
    DOWN = "Down"


class Status(BaseModel):
    status: StatusEnum
    status_message: str
    max_deployments: int | None = None
    deployments: list[str] | None = None
