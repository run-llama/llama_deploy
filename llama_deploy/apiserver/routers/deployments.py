from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from llama_deploy.apiserver.server import manager
from llama_deploy.apiserver.config_parser import Config
from llama_deploy.types import TaskDefinition

deployments_router = APIRouter(
    prefix="/deployments",
)


@deployments_router.get("/")
async def read_deployments() -> JSONResponse:
    """Returns a list of active deployments."""
    return JSONResponse(
        {
            "deployments": list(manager._deployments.keys()),
        }
    )


@deployments_router.get("/{deployment_name}")
async def read_deployment(deployment_name: str) -> JSONResponse:
    """Returns the details of a specific deployment."""
    if deployment_name not in manager.deployment_names:
        raise HTTPException(status_code=404, detail="Deployment not found")

    return JSONResponse(
        {
            f"{deployment_name}": "Up!",
        }
    )


@deployments_router.post("/{deployment_name}/tasks/create")
async def create_deployment_task(
    deployment_name: str, task_definition: TaskDefinition
) -> JSONResponse:
    """Create a task for the deployment."""
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    client = deployment.client
    session = await client.create_session()
    result = await session.get_task_result(await session.create_task(task_definition))

    return JSONResponse(result.model_dump_json() if result else {})


@deployments_router.post("/create/")
async def create_deployment(config_file: UploadFile = File(...)) -> JSONResponse:
    """Creates a new deployment by uploading a configuration file."""
    config = Config.from_yaml_bytes(await config_file.read())
    manager.deploy(config)

    # Return some details about the file
    return JSONResponse(
        {
            "name": config.name,
        }
    )
