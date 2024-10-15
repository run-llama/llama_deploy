import asyncio
from llama_index.core.workflow import (
    Context,
    Workflow,
    StartEvent,
    StopEvent,
    step,
)
from llama_deploy import deploy_workflow, ControlPlaneConfig, WorkflowServiceConfig


class SessionWorkflow(Workflow):
    @step()
    async def step_1(self, ctx: Context, ev: StartEvent) -> StopEvent:
        cur_val = await ctx.get("count", default=0)
        await ctx.set("count", cur_val + 1)

        return StopEvent(result=cur_val + 1)


session_workflow = SessionWorkflow(timeout=10)


async def main():
    # sanity check
    result = await session_workflow.run(arg1="hello_world")
    assert result == 1, "Sanity check failed"

    outer_task = asyncio.create_task(
        deploy_workflow(
            session_workflow,
            WorkflowServiceConfig(
                host="127.0.0.1",
                port=8002,
                service_name="session_workflow",
            ),
            ControlPlaneConfig(),
        )
    )

    await asyncio.gather(outer_task)


if __name__ == "__main__":
    asyncio.run(main())
