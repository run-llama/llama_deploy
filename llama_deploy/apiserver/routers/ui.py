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

    headers = dict(request.headers)
    headers.pop("accept-encoding", None)
    headers.pop("Accept-Encoding", None)

    try:
        response = await client.request(
            method=request.method,
            url=f"http://localhost:3000/{path}",
            headers=headers,
            content=await request.body(),
            params=dict(request.query_params),
        )
        return Response(
            content=response.content, status_code=response.status_code, headers=headers
        )

    except httpx.TimeoutException:
        return Response()
