from llama_index.core.workflow import (
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
from llama_index.core.workflow.events import (
    HumanResponseEvent,
    InputRequiredEvent,
)


class HumanInTheLoopWorkflow(Workflow):
    @step
    async def step1(self, ev: StartEvent) -> InputRequiredEvent:
        return InputRequiredEvent(prefix="Enter a number: ")

    @step
    async def step2(self, ev: HumanResponseEvent) -> StopEvent:
        return StopEvent(result=ev.response)


workflow = HumanInTheLoopWorkflow()
