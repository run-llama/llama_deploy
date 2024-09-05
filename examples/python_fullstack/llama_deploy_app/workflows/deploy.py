import asyncio
import time
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

from llama_deploy import deploy_workflow, WorkflowServiceConfig

from rag_workflow import build_rag_workflow
from agent_workflow import build_agentic_workflow


class DeployConfig(BaseSettings):
    """
    Controls which workflow is deployed.

    Configured with env var DEPLOY_SETTINGS_NAME.
    """

    model_config = SettingsConfigDict(env_prefix="DEPLOY_SETTINGS_")

    name: Literal["agentic_workflow", "rag_workflow"] = "agentic_workflow"


async def deploy_agentic_workflow():
    rag_workflow = build_rag_workflow()
    agentic_workflow = build_agentic_workflow(rag_workflow)

    await deploy_workflow(
        agentic_workflow,
        WorkflowServiceConfig(
            host="agentic_workflow",
            port=8003,
            internal_host="0.0.0.0",
            internal_port=8003,
            service_name="agentic_workflow",
            description="Agentic workflow",
        ),
        # config controlled by env vars
        # control_plane_config=ControlPlaneConfig(),
    )


async def deploy_rag_workflow():
    rag_workflow = build_rag_workflow()

    await deploy_workflow(
        rag_workflow,
        WorkflowServiceConfig(
            host="rag_workflow",
            port=8002,
            internal_host="0.0.0.0",
            internal_port=8002,
            # service name matches the name of the workflow used in Agentic Workflow
            service_name="rag_workflow",
            description="RAG workflow",
        ),
        # Config controlled by env vars
        # control_plane_config=ControlPlaneConfig(),
    )


if __name__ == "__main__":
    # reads from env vars, specifically DEPLOY_SETTINGS_NAME
    deployment = DeployConfig()

    # delay the startup to allow core services to spin up
    time.sleep(5)

    if deployment.name == "agentic_workflow":
        asyncio.run(deploy_agentic_workflow())
    elif deployment.name == "rag_workflow":
        asyncio.run(deploy_rag_workflow())
    else:
        raise ValueError(f"Invalid deployment name: {deployment.name}")
