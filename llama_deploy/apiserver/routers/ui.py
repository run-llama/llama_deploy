from typing import List, Optional
import httpx
import asyncio
from fastapi import APIRouter, Request, WebSocket
from fastapi.exceptions import HTTPException
from starlette.responses import StreamingResponse
from starlette.background import BackgroundTask
import websockets
import logging

from llama_deploy.apiserver.server import manager

logger = logging.getLogger(__name__)

ui_router = APIRouter(
    prefix="/ui",
)

UPSTREAM_HTTP = "http://localhost:3000"
UPSTREAM_WS = "ws://localhost:3000"


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


@ui_router.websocket("/{deployment_name}/{path:path}")
@ui_router.websocket("/{deployment_name}")
async def websocket_proxy(
    websocket: WebSocket,
    deployment_name: str,
    path: str | None = None,
) -> None:
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        await websocket.close(code=1008, reason="Deployment not found")
        return

    # Build the upstream WebSocket URL using FastAPI's extracted path parameter
    slash_path = f"/{path}" if path else ""
    upstream_path = f"/ui/{deployment_name}{slash_path}"

    # Convert to WebSocket URL
    upstream_url = f"{UPSTREAM_WS}{upstream_path}"
    if websocket.url.query:
        upstream_url += f"?{websocket.url.query}"

    logger.debug(f"Proxying WebSocket {websocket.url} -> {upstream_url}")

    await _ws_proxy(websocket, upstream_url)


@ui_router.api_route(
    "/{deployment_name}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
)
@ui_router.api_route(
    "/{deployment_name}",
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

    # Build the upstream URL using FastAPI's extracted path parameter
    slash_path = f"/{path}" if path else ""
    upstream_path = f"/ui/{deployment_name}{slash_path}"

    upstream_url = httpx.URL(f"{UPSTREAM_HTTP}{upstream_path}").copy_with(
        params=request.query_params
    )

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
