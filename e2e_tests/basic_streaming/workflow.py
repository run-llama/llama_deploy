from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)


class ProgressEvent(Event):
    progress: float


class Step1(Event):
    arg1: str


class Step2(Event):
    arg1: str


class StreamingWorkflow(Workflow):
    @step()
    async def run_step_1(self, ctx: Context, ev: StartEvent) -> Step1:
        arg1 = ev.get("arg1")
        if not arg1:
            raise ValueError("arg1 is required.")

        ctx.write_event_to_stream(ProgressEvent(progress=0.3))

        return Step1(arg1=str(arg1) + "_result")

    @step()
    async def run_step_2(self, ctx: Context, ev: Step1) -> Step2:
        arg1 = ev.arg1
        if not arg1:
            raise ValueError("arg1 is required.")

        ctx.write_event_to_stream(ProgressEvent(progress=0.6))

        return Step2(arg1=str(arg1) + "_result")

    @step()
    async def run_step_3(self, ctx: Context, ev: Step2) -> StopEvent:
        arg1 = ev.arg1
        if not arg1:
            raise ValueError("arg1 is required.")

        ctx.write_event_to_stream(ProgressEvent(progress=0.9))

        return StopEvent(result=str(arg1) + "_result")
