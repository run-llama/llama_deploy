import asyncio

from llama_index.core.workflow import Context, StartEvent, StopEvent, Workflow, step


# create a dummy workflow
class CounterWorkflow(Workflow):
    """A dummy workflow with only one step sending back the input given."""

    @step()
    async def run_step(self, ctx: Context, ev: StartEvent) -> StopEvent:
        amount = float(ev.get("amount", 0.0))
        total = await ctx.get("total", 0.0) + amount
        await ctx.set("total", total)
        return StopEvent(result=f"Current balance: {total}")


counter_workflow = CounterWorkflow()


async def main():
    print(await counter_workflow.run(message=10.0))


if __name__ == "__main__":
    asyncio.run(main())
