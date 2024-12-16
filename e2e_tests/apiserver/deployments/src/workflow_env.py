import asyncio
import os

from llama_index.core.workflow import (
    Context,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)


class MyWorkflow(Workflow):
    @step()
    async def run_step(self, ctx: Context, ev: StartEvent) -> StopEvent:
        var_1 = os.environ.get("VAR_1")
        var_2 = os.environ.get("VAR_2")
        api_key = os.environ.get("API_KEY")
        return StopEvent(
            # result depends on variables read from environment
            result=(f"var_1: {var_1}, " f"var_2: {var_2}, " f"api_key: {api_key}")
        )


workflow = MyWorkflow()


async def main(w: Workflow):
    h = w.run()
    print(await h)


if __name__ == "__main__":
    import os

    # set env variables
    os.environ["VAR_1"] = "x"
    os.environ["VAR_1"] = "y"
    os.environ["API_KEY"] = "123"

    w = MyWorkflow()

    asyncio.run(main(w))
