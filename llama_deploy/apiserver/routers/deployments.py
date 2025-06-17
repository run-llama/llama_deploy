import asyncio
import json
import logging
from typing import AsyncGenerator, List, Optional

import httpx
import websockets
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, WebSocket
from fastapi.responses import JSONResponse, StreamingResponse
from llama_index.core.workflow.context_serializers import JsonSerializer
from starlette.background import BackgroundTask

from llama_deploy.apiserver.deployment_config_parser import DeploymentConfig
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
logger = logging.getLogger(__name__)


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
    deployment_name: str, task_definition: TaskDefinition, session_id: str | None = None
) -> JSONResponse:
    """Create a task for the deployment, wait for result and delete associated session."""
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    if task_definition.service_id is None:
        if deployment.default_service is None:
            raise HTTPException(
                status_code=400,
                detail="Service is None and deployment has no default service",
            )
        task_definition.service_id = deployment.default_service
    elif task_definition.service_id not in deployment.service_names:
        raise HTTPException(
            status_code=404,
            detail=f"Service '{task_definition.service_id}' not found in deployment 'deployment_name'",
        )

    if session_id:
        session = await deployment.client.core.sessions.get(session_id)
    else:
        session = await deployment.client.core.sessions.create()

    result = await session.run(
        task_definition.service_id or "", **json.loads(task_definition.input)
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

    if task_definition.service_id is None:
        if deployment.default_service is None:
            raise HTTPException(
                status_code=400,
                detail="Service is None and deployment has no default service",
            )
        task_definition.service_id = deployment.default_service

    if session_id:
        session = await deployment.client.core.sessions.get(session_id)
    else:
        session = await deployment.client.core.sessions.create()
        session_id = session.id

    task_definition.session_id = session_id
    task_definition.task_id = await session.run_nowait(
        task_definition.service_id or "", **json.loads(task_definition.input)
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
    deployment_name: str,
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
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    session = await deployment.client.core.sessions.get(session_id)
    serializer_fn = JsonSerializer().serialize if raw_event else json.dumps

    async def event_stream() -> AsyncGenerator[str, None]:
        # need to convert back to str to use SSE
        async for event in session.get_task_result_stream(task_id):
            yield serializer_fn(event) + "\n"

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
    deployment_name: str,
    path: str | None = None,
) -> None:
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        await websocket.close(code=1008, reason="Deployment not found")
        return

    if deployment._config.ui is None:
        raise HTTPException(status_code=404, detail="Deployment has no ui configured")

    # Build the upstream WebSocket URL using FastAPI's extracted path parameter
    slash_path = f"/{path}" if path else ""
    upstream_path = f"/deployments/{deployment_name}/ui{slash_path}"

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
    deployment_name: str,
    path: str | None = None,
) -> StreamingResponse:
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    if deployment._config.ui is None:
        raise HTTPException(status_code=404, detail="Deployment has no ui configured")

    # Build the upstream URL using FastAPI's extracted path parameter
    slash_path = f"/{path}" if path else ""
    upstream_path = f"/deployments/{deployment_name}/ui{slash_path}"

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
