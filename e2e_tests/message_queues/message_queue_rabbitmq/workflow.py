from llama_index.core.workflow import Context, StartEvent, StopEvent, Workflow, step


class BasicWorkflow(Workflow):
    def __init__(self, *args, **kwargs):
        self._name = kwargs.pop("name")
        super().__init__(*args, **kwargs)

    @step()
    async def run_step(self, ctx: Context, ev: StartEvent) -> StopEvent:
        received = ev.get("arg")
        return StopEvent(result=f"{self._name} received {received}")
