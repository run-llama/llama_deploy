from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)


class CustomEvent(Event):
    pass


class OuterWorkflow(Workflow):
    @step()
    async def run_step(self, ctx: Context, ev: StartEvent) -> CustomEvent:
        await ctx.set("arg1", ev.get("arg1"))
        # ensure the collect_events system serializes correctly
        ctx.collect_events(ev, [CustomEvent])
        return CustomEvent()

    @step
    async def run_final_step(self, ctx: Context, ev: CustomEvent) -> StopEvent:
        arg1 = await ctx.get("arg1")
        return StopEvent(result=str(arg1) + "_result")
