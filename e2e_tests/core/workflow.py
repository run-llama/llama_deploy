from llama_index.core.workflow import Context, StartEvent, StopEvent, Workflow, step


class BasicWorkflow(Workflow):
    @step()
    async def run_step(self, ctx: Context, ev: StartEvent) -> StopEvent:
        arg1 = ev.get("arg1")
        if not arg1:
            raise ValueError("arg1 is required.")

        return StopEvent(result=str(arg1) + "_result")
