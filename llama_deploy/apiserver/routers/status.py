from fastapi import APIRouter

from llama_deploy.apiserver.server import manager
from llama_deploy.types.apiserver import Status, StatusEnum

status_router = APIRouter(
    prefix="/status",
)


@status_router.get("/")
async def status() -> Status:
    return Status(
        status=StatusEnum.HEALTHY,
        max_deployments=manager._max_deployments,
        deployments=list(manager._deployments.keys()),
        status_message="",
    )
