import logging
import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI

from .deployment import Manager
from .deployment_config_parser import DeploymentConfig
from .settings import ApiserverSettings
from .stats import apiserver_state

logger = logging.getLogger("uvicorn.info")
manager = Manager(
    deployments_path=Path(tempfile.gettempdir()) / "llama_deploy" / "deployments"
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    apiserver_state.state("starting")
    settings = ApiserverSettings()
    t = manager.serve()
    logger.info(f"deployments folder: {manager._deployments_path}")
    logger.info(f"rc folder: {settings.rc_path}")

    if settings.rc_path.exists():
        logger.info(
            f"Browsing the rc folder {settings.rc_path} for deployments to start"
        )
        # match both .yml and .yaml files with the glob
        for yaml_file in settings.rc_path.glob("*.y*ml"):
            try:
                logger.info(f"Deploying startup configuration from {yaml_file}")
                config = DeploymentConfig.from_yaml(yaml_file)
                await manager.deploy(config)
            except Exception as e:
                logger.error(f"Failed to deploy {yaml_file}: {str(e)}")

    apiserver_state.state("running")
    yield

    t.close()
    # Clean up deployments folder
    if os.path.exists(manager._deployments_path.resolve()):
        shutil.rmtree(manager._deployments_path.resolve())
    apiserver_state.state("stopped")
