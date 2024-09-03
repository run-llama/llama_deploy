from llama_deploy import deploy_workflow, WorkflowServiceConfig

from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step
from llama_index.llms.openai import OpenAI

from multi_workflows_rabbitmq.core import control_plane_config


class FunnyJokeWorkflow(Workflow):
    @step
    async def add_funny_joke_step(self, ev: StartEvent) -> StopEvent:
        # Your workflow logic here
        input = str(ev.get("input", ""))
        llm = OpenAI("gpt-4o-mini")
        response = await llm.acomplete("Tell a funny data joke.")
        result = input + "\n\nAnd here is a funny joke:\n\n" + response.text
        return StopEvent(result=result)


# Local Testing
async def _test_workflow():
    w = FunnyJokeWorkflow(timeout=60, verbose=False)
    result = await w.run(input="A baby llama is called a cria.")
    print(str(result))


if __name__ == "__main__":
    import asyncio

    # asyncio.run(_test_workflow())

    asyncio.run(
        deploy_workflow(
            workflow=FunnyJokeWorkflow(),
            workflow_config=WorkflowServiceConfig(
                host="127.0.0.1", port=8001, service_name="funny_joke_workflow"
            ),
            control_plane_config=control_plane_config,
        )
    )
