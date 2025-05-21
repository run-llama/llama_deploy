import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI

from .deployment import Manager
from .deployment_config_parser import DeploymentConfig
from .settings import settings
from .stats import apiserver_state

logger = logging.getLogger("uvicorn.info")
manager = Manager()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    apiserver_state.state("starting")

    manager.set_deployments_path(settings.deployments_path)
    t = asyncio.create_task(manager.serve())
    await asyncio.sleep(0)

    logger.info(f"deployments folder: {manager.deployments_path}")
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
                await manager.deploy(config, base_path=str(settings.rc_path))
            except Exception as e:
                logger.error(f"Failed to deploy {yaml_file}: {str(e)}")

    apiserver_state.state("running")
    yield

    t.cancel()

    apiserver_state.state("stopped")
