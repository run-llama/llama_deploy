from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from llama_deploy.apiserver.server import manager
from llama_deploy.apiserver.config_parser import Config


deploy_router = APIRouter(
    prefix="/deployments",
)


@deploy_router.get("/")
async def read_deployments() -> JSONResponse:
    return JSONResponse(
        {
            "deployments": list(manager._deployments.keys()),
        }
    )


@deploy_router.get("/{deployment_name}")
async def read_deployment(deployment_name: str) -> JSONResponse:
    return JSONResponse(
        {
            f"{deployment_name}": "Up!",
        }
    )


@deploy_router.post("/create/")
async def create_deployment(config_file: UploadFile = File(...)) -> JSONResponse:
    config = Config.from_yaml_bytes(await config_file.read())
    manager.deploy(config)

    # Return some details about the file
    return JSONResponse(
        {
            "name": config.name,
        }
    )
