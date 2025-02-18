import httpx
from fastapi import APIRouter
from fastapi.exceptions import HTTPException
from fastapi.responses import PlainTextResponse

from llama_deploy.apiserver.server import manager
from llama_deploy.apiserver.settings import ApiserverSettings
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


@status_router.get("/metrics")
async def metrics() -> PlainTextResponse:
    """Proxies the Prometheus metrics endpoint through the API Server.

    This endpoint is mostly used in serverless environments where the LlamaDeploy
    container cannot expose more than one port (e.g. Knative, Google Cloud Run).
    If Prometheus is not enabled, this endpoint returns an empty HTTP-204 response.
    """
    settings = ApiserverSettings()
    if not settings.prometheus_enabled:
        return PlainTextResponse(status_code=204)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{settings.prometheus_port}/")
            return PlainTextResponse(content=response.text)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
