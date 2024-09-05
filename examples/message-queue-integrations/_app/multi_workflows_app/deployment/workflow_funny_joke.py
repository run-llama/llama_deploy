from llama_deploy import deploy_workflow, WorkflowServiceConfig

from multi_workflows_app.deployment.core import control_plane_config
from multi_workflows_app.workflows.funny_joke import FunnyJokeWorkflow

if __name__ == "__main__":
    import asyncio

    asyncio.run(
        deploy_workflow(
            workflow=FunnyJokeWorkflow(),
            workflow_config=WorkflowServiceConfig(
                service_name="funny_joke_workflow",
            ),
            control_plane_config=control_plane_config,
        )
    )
