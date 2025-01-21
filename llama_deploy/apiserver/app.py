import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routers import deployments_router, status_router
from .server import lifespan

logger = logging.getLogger("uvicorn.info")


app = FastAPI(lifespan=lifespan)

# Configure CORS middleware if the environment variable is set
if not os.environ.get("DISABLE_CORS", False):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allows all origins
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )

app.include_router(deployments_router)
app.include_router(status_router)


@app.get("/")
async def root() -> JSONResponse:
    return JSONResponse(
        {
            "swagger_docs": "http://localhost:4501/docs",
            "status": "http://localhost:4501/status",
        }
    )
