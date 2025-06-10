import asyncio
from typing import Literal

from llama_index.core.workflow import (
    Workflow,
    StartEvent,
    StopEvent,
    step,
    Context,
    Event,
    HumanResponseEvent,
    InputRequiredEvent,
)
from pydantic import Field


class EchoEvent(Event):
    """An event that echoes the input message."""

    message: str = Field(description="The message to echo.")


class WaitEvent(InputRequiredEvent):
    wait_please: Literal[True]


class ContinueEvent(HumanResponseEvent):
    """An event that continues the workflow."""

    continue_please: Literal[True]


# create a dummy workflow
class EchoWorkflow(Workflow):
    """A dummy workflow with only one step sending back the input given."""

    def __init__(self, *args, **kwargs):
        if "timeout" not in kwargs:
            kwargs["timeout"] = None
        super().__init__(*args, **kwargs)

    @step()
    async def run_step(self, ev: StartEvent, ctx: Context) -> StopEvent:
        for i in range(10):
            await asyncio.sleep(1)
            ctx.write_event_to_stream(EchoEvent(message=f"Echoing: {i}"))
        return StopEvent(result="Done!")

    # @step()
    # async def wait_step(self, ev: ContinueEvent, ctx: Context) -> StopEvent:
    #     for i in range(10):
    #         await asyncio.sleep(1)
    #         ctx.write_event_to_stream(EchoEvent(message=f"Echoing: {i}"))
    #     return StopEvent(result="Done!")


echo_workflow = EchoWorkflow()


async def main():
    print(await echo_workflow.run(message="Hello!"))


if __name__ == "__main__":
    asyncio.run(main())
