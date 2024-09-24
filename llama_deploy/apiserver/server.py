import logging
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI

from .deployment import Manager


logger = logging.getLogger("uvicorn.info")
manager = Manager(
    deployments_path=Path(tempfile.gettempdir()) / "llama_deploy" / "deployments"
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    t = manager.serve()
    yield
    t.close()
    shutil.rmtree(manager._deployments_path.resolve())
