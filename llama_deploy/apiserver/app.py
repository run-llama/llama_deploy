import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .routers import status_router, deployments_router
from .server import lifespan

logger = logging.getLogger("uvicorn.info")


app = FastAPI(root_path="/", lifespan=lifespan)
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
