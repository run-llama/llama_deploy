import asyncio
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

    name: Literal["agentic", "rag"] = "agentic"


async def deploy_agentic_workflow():
    rag_workflow = build_rag_workflow()
    agentic_workflow = build_agentic_workflow(rag_workflow)

    await deploy_workflow(
        agentic_workflow,
        WorkflowServiceConfig(
            host="0.0.0.0",
            port=8003,
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
            host="0.0.0.0",
            port=8002,
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

    if deployment.name == "agentic":
        asyncio.run(deploy_agentic_workflow())
    elif deployment.name == "rag":
        asyncio.run(deploy_rag_workflow())
    else:
        raise ValueError(f"Invalid deployment name: {deployment.name}")
