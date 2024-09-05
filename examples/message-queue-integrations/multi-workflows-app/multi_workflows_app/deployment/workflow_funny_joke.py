from llama_deploy import deploy_workflow, WorkflowServiceConfig

from multi_workflows_app.deployment.core import control_plane_config
from multi_workflows_app.workflows.funny_joke import FunnyJokeWorkflow

if __name__ == "__main__":
    import asyncio

    print(f"CONTROL_PLANE_URL: {control_plane_config.url}", flush=True)

    asyncio.run(
        deploy_workflow(
            workflow=FunnyJokeWorkflow(),
            workflow_config=WorkflowServiceConfig(
                host="funny_joke_workflow",
                port=8001,
                internal_host="0.0.0.0",
                internal_port=8001,
                service_name="funny_joke_workflow",
            ),
            control_plane_config=control_plane_config,
        )
    )
