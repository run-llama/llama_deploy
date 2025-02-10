from llama_index.core.workflow import Context, StartEvent, StopEvent, Workflow, step


class EchoWithPrompt(Workflow):
    def __init__(self, prompt_msg):
        super().__init__()
        self._prompt_msg = prompt_msg

    @step
    def do_something(self, ctx: Context, ev: StartEvent) -> StopEvent:
        return StopEvent(result=f"{self._prompt_msg}{ev.data}")
