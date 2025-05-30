import gzip

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.exceptions import HTTPException

from llama_deploy.apiserver.server import manager

ui_router = APIRouter(
    prefix="/ui",
)


@ui_router.api_route(
    "/{deployment_name}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
)
async def proxy(
    request: Request,
    deployment_name: str,
    path: str | None = None,
) -> Response:
    deployment = manager.get_deployment(deployment_name)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    client = httpx.AsyncClient(follow_redirects=True)
    # Tell Nextjs not to compress the response body
    headers = dict(request.headers)
    headers["accept-encoding"] = "identity"

    try:
        response = await client.request(
            method=request.method,
            url=f"http://localhost:3000/ui/{deployment_name}/{path}",
            headers=request.headers,
            content=await request.body(),
            params=dict(request.query_params),
        )

        # Adjust response headers to send back a compressed response body
        resp_headers = dict(response.headers)
        compressed_content = gzip.compress(response.content)
        resp_headers["content-encoding"] = "gzip"
        resp_headers["content-length"] = str(len(compressed_content))

        return Response(
            content=compressed_content,
            status_code=response.status_code,
            headers=resp_headers,
        )

    except httpx.TimeoutException:
        return Response()
