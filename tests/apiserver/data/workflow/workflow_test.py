from llama_index.core.workflow import Context, StartEvent, StopEvent, Workflow, step


class MyWorkflow(Workflow):
    @step
    def do_something(self, ctx: Context, ev: StartEvent) -> StopEvent:
        return StopEvent(result=f"Received: {ev.data}")
