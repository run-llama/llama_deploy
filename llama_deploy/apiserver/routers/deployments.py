import asyncio
import json
import logging
from typing import Annotated, AsyncGenerator, List, Optional

import httpx
import websockets
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
)
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
from workflows import Context
from workflows.context import JsonSerializer
from workflows.handler import WorkflowHandler

from llama_deploy.apiserver.deployment import Deployment
from llama_deploy.apiserver.deployment_config_parser import DeploymentConfig
from llama_deploy.apiserver.server import manager
from llama_deploy.types import (
    DeploymentDefinition,
    EventDefinition,
    SessionDefinition,
    TaskDefinition,
)
from llama_deploy.types.core import TaskResult, generate_id

deployments_router = APIRouter(
    prefix="/deployments",
)
logger = logging.getLogger(__name__)


def deployment(deployment_name: str) -> Deployment:
    """FastAPI dependency to retrieve a Deployment instance"""
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return deployment


@deployments_router.get("/")
async def read_deployments() -> list[DeploymentDefinition]:
    """Returns a list of active deployments."""
    return [DeploymentDefinition(name=k) for k in manager._deployments.keys()]


@deployments_router.get("/{deployment_name}")
async def read_deployment(
    deployment: Annotated[Deployment, Depends(deployment)],
) -> DeploymentDefinition:
    """Returns the details of a specific deployment."""

    return DeploymentDefinition(name=deployment.name)


@deployments_router.post("/create")
async def create_deployment(
    base_path: str = ".",
    config_file: UploadFile = File(...),
    reload: bool = False,
    local: bool = False,
) -> DeploymentDefinition:
    """Creates a new deployment by uploading a configuration file."""
    config = DeploymentConfig.from_yaml_bytes(await config_file.read())
    await manager.deploy(config, base_path, reload, local)

    return DeploymentDefinition(name=config.name)


@deployments_router.post("/{deployment_name}/tasks/run")
async def create_deployment_task(
    deployment: Annotated[Deployment, Depends(deployment)],
    task_definition: TaskDefinition,
    session_id: str | None = None,
) -> JSONResponse:
    """Create a task for the deployment, wait for result and delete associated session."""

    service_id = task_definition.service_id or deployment.default_service
    if service_id is None:
        raise HTTPException(
            status_code=400,
            detail="Service is None and deployment has no default service",
        )

    if service_id not in deployment.service_names:
        raise HTTPException(
            status_code=404,
            detail=f"Service '{task_definition.service_id}' not found in deployment 'deployment_name'",
        )

    run_kwargs = json.loads(task_definition.input) if task_definition.input else {}
    session_id = session_id or task_definition.session_id
    result = await deployment.run_workflow(
        service_id=service_id, session_id=session_id, **run_kwargs
    )
    return JSONResponse(result)


@deployments_router.post("/{deployment_name}/tasks/create")
async def create_deployment_task_nowait(
    deployment: Annotated[Deployment, Depends(deployment)],
    task_definition: TaskDefinition,
    session_id: str | None = None,
) -> TaskDefinition:
    """Create a task for the deployment but don't wait for result."""
    service_id = task_definition.service_id or deployment.default_service
    if service_id is None:
        raise HTTPException(
            status_code=400,
            detail="Service is None and deployment has no default service",
        )

    if service_id not in deployment.service_names:
        raise HTTPException(
            status_code=404,
            detail=f"Service '{task_definition.service_id}' not found in deployment 'deployment_name'",
        )

    run_kwargs = json.loads(task_definition.input) if task_definition.input else {}
    session_id = session_id or task_definition.session_id
    handler_id, session_id = deployment.run_workflow_no_wait(
        service_id=service_id, session_id=session_id, **run_kwargs
    )

    task_definition.session_id = session_id
    task_definition.task_id = handler_id

    return task_definition


@deployments_router.post("/{deployment_name}/tasks/{task_id}/events")
async def send_event(
    deployment: Annotated[Deployment, Depends(deployment)],
    task_id: str,
    session_id: str,
    event_def: EventDefinition,
) -> EventDefinition:
    """Send a human response event to a service for a specific task and session."""
    ctx = deployment._contexts[session_id]
    serializer = JsonSerializer()
    event = serializer.deserialize(event_def.event_obj_str)
    ctx.send_event(event)

    return event_def


@deployments_router.get("/{deployment_name}/tasks/{task_id}/events")
async def get_events(
    deployment: Annotated[Deployment, Depends(deployment)],
    session_id: str,
    task_id: str,
    raw_event: bool = False,
) -> StreamingResponse:
    """
    Get the stream of events from a given task and session.

    Args:
        raw_event (bool, default=False): Whether to return the raw event object
            or just the event data.
    """

    async def event_stream(handler: WorkflowHandler) -> AsyncGenerator[str, None]:
        serializer = JsonSerializer()
        # need to convert back to str to use SSE
        async for event in handler.stream_events():
            data = json.loads(serializer.serialize(event))
            if raw_event:
                yield json.dumps(data) + "\n"
            else:
                yield json.dumps(data.get("value")) + "\n"
            await asyncio.sleep(0.01)
        await handler

    try:
        deployment_handler = deployment._handlers[task_id]
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")

    return StreamingResponse(
        event_stream(deployment_handler),
        media_type="application/x-ndjson",
    )


@deployments_router.get("/{deployment_name}/tasks/{task_id}/results")
async def get_task_result(
    deployment: Annotated[Deployment, Depends(deployment)],
    session_id: str,
    task_id: str,
) -> TaskResult | None:
    """Get the task result associated with a task and session."""

    try:
        handler = deployment._handlers[task_id]
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")
    result = await handler
    if not isinstance(result, str):
        result = str(result)
    return TaskResult(task_id=task_id, history=[], result=result)


@deployments_router.post("/{deployment_name}/tasks/delete")
async def delete_task(
    deployment: Annotated[Deployment, Depends(deployment)], task_id: str
) -> None:
    """Get the active sessions in a deployment and service."""

    if task_id not in deployment._handlers:
        raise HTTPException(status_code=404, detail="Task not found")

    deployment._handlers.pop(task_id)  # noqa: ignore
    deployment._handler_inputs.pop(task_id, None)  # noqa: ignore


@deployments_router.get("/{deployment_name}/tasks")
async def get_tasks(
    deployment: Annotated[Deployment, Depends(deployment)],
) -> list[TaskDefinition]:
    """Get all the tasks from all the sessions in a given deployment."""

    tasks: list[TaskDefinition] = []
    for task_id in deployment._handlers.keys():
        tasks.append(
            TaskDefinition(task_id=task_id, input=deployment._handler_inputs[task_id])
        )

    return tasks


@deployments_router.get("/{deployment_name}/sessions")
async def get_sessions(
    deployment: Annotated[Deployment, Depends(deployment)],
) -> list[SessionDefinition]:
    """Get the active sessions in a deployment and service."""

    return [SessionDefinition(session_id=k) for k in deployment._contexts.keys()]


@deployments_router.get("/{deployment_name}/sessions/{session_id}")
async def get_session(
    deployment: Annotated[Deployment, Depends(deployment)], session_id: str
) -> SessionDefinition:
    """Get the definition of a session by ID."""

    if session_id not in deployment._contexts:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionDefinition(session_id=session_id)


@deployments_router.post("/{deployment_name}/sessions/create")
async def create_session(
    deployment: Annotated[Deployment, Depends(deployment)],
) -> SessionDefinition:
    """Create a new session for a deployment."""

    workflow = deployment._workflow_services[deployment.default_service]
    session_id = generate_id()
    deployment._contexts[session_id] = Context(workflow)

    return SessionDefinition(session_id=session_id)


@deployments_router.post("/{deployment_name}/sessions/delete")
async def delete_session(
    deployment: Annotated[Deployment, Depends(deployment)], session_id: str
) -> None:
    """Get the active sessions in a deployment and service."""

    if session_id not in deployment._contexts:
        raise HTTPException(status_code=404, detail="Session not found")

    deployment._contexts.pop(session_id)


async def _ws_proxy(ws: WebSocket, upstream_url: str) -> None:
    """Proxy WebSocket connection to upstream server."""
    await ws.accept()

    # Forward most headers except WebSocket-specific ones
    header_blacklist = {
        "host",
        "connection",
        "upgrade",
        "sec-websocket-key",
        "sec-websocket-version",
        "sec-websocket-extensions",
    }
    hdrs = [(k, v) for k, v in ws.headers.items() if k.lower() not in header_blacklist]

    try:
        # Parse subprotocols if present
        subprotocols: Optional[List[websockets.Subprotocol]] = None
        if "sec-websocket-protocol" in ws.headers:
            # Parse comma-separated subprotocols
            subprotocols = [
                websockets.Subprotocol(p.strip())
                for p in ws.headers["sec-websocket-protocol"].split(",")
            ]

        # Open upstream WebSocket connection
        async with websockets.connect(
            upstream_url,
            additional_headers=hdrs,
            subprotocols=subprotocols,
            open_timeout=None,
            ping_interval=None,
        ) as upstream:

            async def client_to_upstream() -> None:
                try:
                    while True:
                        msg = await ws.receive()
                        if msg["type"] == "websocket.receive":
                            if "text" in msg:
                                await upstream.send(msg["text"])
                            elif "bytes" in msg:
                                await upstream.send(msg["bytes"])
                        elif msg["type"] == "websocket.disconnect":
                            break
                except Exception as e:
                    logger.debug(f"Client to upstream connection ended: {e}")

            async def upstream_to_client() -> None:
                try:
                    async for message in upstream:
                        if isinstance(message, str):
                            await ws.send_text(message)
                        else:
                            await ws.send_bytes(message)
                except Exception as e:
                    logger.debug(f"Upstream to client connection ended: {e}")

            # Pump both directions concurrently
            await asyncio.gather(
                client_to_upstream(), upstream_to_client(), return_exceptions=True
            )

    except Exception as e:
        logger.error(f"WebSocket proxy error: {e}")
    finally:
        try:
            await ws.close()
        except Exception as e:
            logger.debug(f"Error closing client connection: {e}")


@deployments_router.websocket("/{deployment_name}/ui/{path:path}")
@deployments_router.websocket("/{deployment_name}/ui")
async def websocket_proxy(
    websocket: WebSocket,
    deployment: Annotated[Deployment, Depends(deployment)],
    path: str | None = None,
) -> None:
    if deployment._config.ui is None:
        raise HTTPException(status_code=404, detail="Deployment has no ui configured")

    # Build the upstream WebSocket URL using FastAPI's extracted path parameter
    slash_path = f"/{path}" if path else ""
    upstream_path = f"/deployments/{deployment.name}/ui{slash_path}"

    # Convert to WebSocket URL
    upstream_url = f"ws://localhost:{deployment._config.ui.port}{upstream_path}"
    if websocket.url.query:
        upstream_url += f"?{websocket.url.query}"

    logger.debug(f"Proxying WebSocket {websocket.url} -> {upstream_url}")

    await _ws_proxy(websocket, upstream_url)


@deployments_router.api_route(
    "/{deployment_name}/ui/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
)
@deployments_router.api_route(
    "/{deployment_name}/ui",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
)
async def proxy(
    request: Request,
    deployment: Annotated[Deployment, Depends(deployment)],
    path: str | None = None,
) -> StreamingResponse:
    if deployment._config.ui is None:
        raise HTTPException(status_code=404, detail="Deployment has no ui configured")

    # Build the upstream URL using FastAPI's extracted path parameter
    slash_path = f"/{path}" if path else ""
    upstream_path = f"/deployments/{deployment.name}/ui{slash_path}"

    upstream_url = httpx.URL(
        f"http://localhost:{deployment._config.ui.port}{upstream_path}"
    ).copy_with(params=request.query_params)

    # Debug logging
    logger.debug(f"Proxying {request.method} {request.url} -> {upstream_url}")

    # Strip hop-by-hop headers + host
    hop_by_hop = {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",  # codespell:ignore
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
    }
    headers = {k: v for k, v in request.headers.items() if k.lower() not in hop_by_hop}

    try:
        client = httpx.AsyncClient(timeout=None)

        req = client.build_request(
            request.method,
            upstream_url,
            headers=headers,
            content=request.stream(),  # stream uploads
        )
        upstream = await client.send(req, stream=True)

        resp_headers = {
            k: v for k, v in upstream.headers.items() if k.lower() not in hop_by_hop
        }

        # Close client when upstream response is done
        async def cleanup() -> None:
            await upstream.aclose()
            await client.aclose()

        return StreamingResponse(
            upstream.aiter_raw(),  # stream downloads
            status_code=upstream.status_code,
            headers=resp_headers,
            background=BackgroundTask(cleanup),  # tidy up when finished
        )

    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Upstream server unavailable")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Upstream server timeout")
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        raise HTTPException(status_code=502, detail="Proxy error")
