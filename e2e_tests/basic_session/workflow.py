from llama_index.core.workflow import (
    Context,
    Workflow,
    StartEvent,
    StopEvent,
    step,
)


class SessionWorkflow(Workflow):
    @step()
    async def step_1(self, ctx: Context, ev: StartEvent) -> StopEvent:
        cur_val = await ctx.get("count", default=0)
        await ctx.set("count", cur_val + 1)

        return StopEvent(result=cur_val + 1)
