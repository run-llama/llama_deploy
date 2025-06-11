import asyncio
from typing import Literal

from llama_index.core.workflow import (
    Workflow,
    StartEvent,
    StopEvent,
    step,
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

    @step
    async def step1(self, ev: StartEvent) -> InputRequiredEvent:
        return InputRequiredEvent(prefix="Enter a number: ")

    @step
    async def step2(self, ev: HumanResponseEvent) -> StopEvent:
        return StopEvent(result=ev.response)


echo_workflow = EchoWorkflow()


async def main():
    print(await echo_workflow.run(message="Hello!"))


if __name__ == "__main__":
    asyncio.run(main())
