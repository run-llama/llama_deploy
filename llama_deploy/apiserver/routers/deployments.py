import json
from typing import AsyncGenerator

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from llama_deploy.apiserver.config_parser import Config
from llama_deploy.apiserver.server import manager
from llama_deploy.types import (
    DeploymentDefinition,
    EventDefinition,
    SessionDefinition,
    TaskDefinition,
)
from llama_deploy.types.core import TaskResult

deployments_router = APIRouter(
    prefix="/deployments",
)


@deployments_router.get("/")
async def read_deployments() -> list[DeploymentDefinition]:
    """Returns a list of active deployments."""
    return [DeploymentDefinition(name=k) for k in manager._deployments.keys()]


@deployments_router.get("/{deployment_name}")
async def read_deployment(deployment_name: str) -> DeploymentDefinition:
    """Returns the details of a specific deployment."""
    if deployment_name not in manager.deployment_names:
        raise HTTPException(status_code=404, detail="Deployment not found")

    return DeploymentDefinition(name=deployment_name)


@deployments_router.post("/create")
async def create_deployment(
    config_file: UploadFile = File(...), reload: bool = False
) -> DeploymentDefinition:
    """Creates a new deployment by uploading a configuration file."""
    config = Config.from_yaml_bytes(await config_file.read())
    await manager.deploy(config, reload)

    return DeploymentDefinition(name=config.name)


@deployments_router.post("/{deployment_name}/tasks/run")
async def create_deployment_task(
    deployment_name: str, task_definition: TaskDefinition, session_id: str | None = None
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

    if session_id:
        session = await deployment.client.core.sessions.get(session_id)
    else:
        session = await deployment.client.core.sessions.create()

    result = await session.run(
        task_definition.agent_id or "", **json.loads(task_definition.input)
    )

    # Assume the request does not care about the session if no session_id is provided
    if session_id is None:
        await deployment.client.core.sessions.delete(session.id)

    return JSONResponse(result)


@deployments_router.post("/{deployment_name}/tasks/create")
async def create_deployment_task_nowait(
    deployment_name: str, task_definition: TaskDefinition, session_id: str | None = None
) -> TaskDefinition:
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

    if session_id:
        session = await deployment.client.core.sessions.get(session_id)
    else:
        session = await deployment.client.core.sessions.create()
        session_id = session.id

    task_definition.session_id = session_id
    task_definition.task_id = await session.run_nowait(
        task_definition.agent_id or "", **json.loads(task_definition.input)
    )

    return task_definition


@deployments_router.post("/{deployment_name}/tasks/{task_id}/events")
async def send_event(
    deployment_name: str,
    task_id: str,
    session_id: str,
    event_def: EventDefinition,
) -> EventDefinition:
    """Send a human response event to a service for a specific task and session."""
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    session = await deployment.client.core.sessions.get(session_id)

    await session.send_event_def(task_id=task_id, ev_def=event_def)

    return event_def


@deployments_router.get("/{deployment_name}/tasks/{task_id}/events")
async def get_events(
    deployment_name: str, session_id: str, task_id: str
) -> StreamingResponse:
    """Get the stream of events from a given task and session."""
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    session = await deployment.client.core.sessions.get(session_id)

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
) -> TaskResult | None:
    """Get the task result associated with a task and session."""
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    session = await deployment.client.core.sessions.get(session_id)
    return await session.get_task_result(task_id)


@deployments_router.get("/{deployment_name}/tasks")
async def get_tasks(
    deployment_name: str,
) -> list[TaskDefinition]:
    """Get all the tasks from all the sessions in a given deployment."""
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    tasks: list[TaskDefinition] = []
    for session in await deployment.client.core.sessions.list():
        for task_def in await session.get_tasks():
            tasks.append(task_def)
    return tasks


@deployments_router.get("/{deployment_name}/sessions")
async def get_sessions(
    deployment_name: str,
) -> list[SessionDefinition]:
    """Get the active sessions in a deployment and service."""
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    sessions = await deployment.client.core.sessions.list()
    return [SessionDefinition(session_id=s.id) for s in sessions]


@deployments_router.get("/{deployment_name}/sessions/{session_id}")
async def get_session(deployment_name: str, session_id: str) -> SessionDefinition:
    """Get the definition of a session by ID."""
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    session = await deployment.client.core.sessions.get(session_id)
    return SessionDefinition(session_id=session.id)


@deployments_router.post("/{deployment_name}/sessions/create")
async def create_session(deployment_name: str) -> SessionDefinition:
    """Create a new session for a deployment."""
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    session = await deployment.client.core.sessions.create()
    return SessionDefinition(session_id=session.id)


@deployments_router.post("/{deployment_name}/sessions/delete")
async def delete_session(deployment_name: str, session_id: str) -> None:
    """Get the active sessions in a deployment and service."""
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    await deployment.client.core.sessions.delete(session_id)
