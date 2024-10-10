import json

from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from typing import AsyncGenerator

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


@deployments_router.post("/create")
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


@deployments_router.post("/{deployment_name}/tasks/run")
async def create_deployment_task(
    deployment_name: str, task_definition: TaskDefinition
) -> JSONResponse:
    """Create a task for the deployment, wait for result and delete associated session."""
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    if task_definition.agent_id is None:
        if deployment.default_service is None:
            raise HTTPException(
                status_code=400,
                detail="Service is None and deployment has no default service",
            )
        task_definition.agent_id = deployment.default_service

    session = await deployment.client.create_session()
    result = await session.run(
        task_definition.agent_id or "", **json.loads(task_definition.input)
    )
    await deployment.client.delete_session(session.session_id)

    return JSONResponse(result)


@deployments_router.post("/{deployment_name}/tasks/create")
async def create_deployment_task_nowait(
    deployment_name: str, task_definition: TaskDefinition
) -> JSONResponse:
    """Create a task for the deployment but don't wait for result."""
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    if task_definition.agent_id is None:
        if deployment.default_service is None:
            raise HTTPException(
                status_code=400,
                detail="Service is None and deployment has no default service",
            )
        task_definition.agent_id = deployment.default_service

    session = await deployment.client.create_session()
    task_id = await session.run_nowait(
        task_definition.agent_id or "", **json.loads(task_definition.input)
    )

    return JSONResponse({"session_id": session.session_id, "task_id": task_id})


@deployments_router.get("/{deployment_name}/tasks/{task_id}/events")
async def get_events(
    deployment_name: str, session_id: str, task_id: str
) -> StreamingResponse:
    """Get the stream of events from a given task and session."""
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    session = await deployment.client.get_session(session_id)

    async def event_stream() -> AsyncGenerator[str, None]:
        # need to convert back to str to use SSE
        async for event in session.get_task_result_stream(task_id):
            yield json.dumps(event) + "\n"

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
    )


@deployments_router.get("/{deployment_name}/tasks/{task_id}/results")
async def get_task_result(
    deployment_name: str, session_id: str, task_id: str
) -> JSONResponse:
    """Get the task result associated with a task and session."""
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    session = await deployment.client.get_session(session_id)
    result = await session.get_task_result(task_id)

    return JSONResponse(result.result if result else "")


@deployments_router.get("/{deployment_name}/sessions")
async def get_sessions(
    deployment_name: str,
) -> JSONResponse:
    """Get the active sessions in a deployment and service."""
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    sessions = await deployment.client.list_sessions()
    return JSONResponse(sessions)


@deployments_router.post("/{deployment_name}/sessions/delete")
async def delete_session(deployment_name: str, session_id: str) -> JSONResponse:
    """Get the active sessions in a deployment and service."""
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    await deployment.client.delete_session(session_id)
    return JSONResponse({"session_id": session_id, "status": "Deleted"})
