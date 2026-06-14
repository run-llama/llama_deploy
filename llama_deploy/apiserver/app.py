import logging
import os
import secrets

from fastapi import FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .routers import deployments_router, status_router
from .server import lifespan
from .settings import settings
from .tracing import configure_tracing

logger = logging.getLogger("uvicorn.info")

_bearer = HTTPBearer(auto_error=False)


def get_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    """FastAPI dependency that validates the Bearer token when an API key is configured.

    When ``LLAMA_DEPLOY_APISERVER_API_KEY`` is not set, all requests are allowed through
    (backward-compatible for local development). When the env var is set, requests must
    supply a matching ``Authorization: Bearer <key>`` header.
    """
    if settings.api_key is None:
        return  # auth disabled — local dev mode
    if credentials is None or not secrets.compare_digest(
        credentials.credentials, settings.api_key
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


app = FastAPI(lifespan=lifespan)

# Setup tracing
configure_tracing(settings)

# Configure CORS middleware if the environment variable is set
if not os.environ.get("DISABLE_CORS", False):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allows all origins
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )

app.include_router(deployments_router, dependencies=[Security(get_api_key)])
app.include_router(status_router)


@app.get("/")
async def root(request: Request) -> JSONResponse:
    return JSONResponse(
        {
            "swagger_docs": f"{request.base_url}docs",
            "status": f"{request.base_url}status",
        }
    )
