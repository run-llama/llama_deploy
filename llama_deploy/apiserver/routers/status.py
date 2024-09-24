from fastapi import APIRouter
from fastapi.responses import JSONResponse

from llama_deploy.apiserver.server import manager


status_router = APIRouter(
    prefix="/status",
)


@status_router.get("/")
async def status() -> JSONResponse:
    return JSONResponse(
        {
            "status": "Up!",
            "max_deployments": manager._max_deployments,
            "deployments": list(manager._deployments.keys()),
        }
    )
