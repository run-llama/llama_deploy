from llama_deploy import deploy_workflow, WorkflowServiceConfig

from multi_workflows_rabbitmq.deployment.core import control_plane_config
from multi_workflows_rabbitmq.workflows.funny_joke import FunnyJokeWorkflow


if __name__ == "__main__":
    import asyncio

    asyncio.run(
        deploy_workflow(
            workflow=FunnyJokeWorkflow(),
            workflow_config=WorkflowServiceConfig(
                host="127.0.0.1", port=8001, service_name="funny_joke_workflow"
            ),
            control_plane_config=control_plane_config,
        )
    )
