import asyncio
from llama_index.core.workflow import Context, Workflow, StartEvent, StopEvent, step
from llama_deploy import deploy_workflow, ControlPlaneConfig, WorkflowServiceConfig


class OuterWorkflow(Workflow):
    @step()
    async def run_step(self, ctx: Context, ev: StartEvent) -> StopEvent:
        arg1 = ev.get("arg1")
        if not arg1:
            raise ValueError("arg1 is required.")

        return StopEvent(result=str(arg1) + "_result")


outer = OuterWorkflow(timeout=10)


async def main():
    # sanity check
    result = await outer.run(arg1="hello_world")
    assert result == "hello_world_result", "Sanity check failed"

    outer_task = asyncio.create_task(
        deploy_workflow(
            outer,
            WorkflowServiceConfig(
                host="127.0.0.1", port=8002, service_name="outer", streaming=True
            ),
            ControlPlaneConfig(),
        )
    )

    await asyncio.gather(outer_task)


if __name__ == "__main__":
    asyncio.run(main())
