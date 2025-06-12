import asyncio

from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step
from pyfiglet import Figlet
from cowpy import cow


# create a dummy workflow
class EchoWorkflow(Workflow):
    """A dummy workflow with only one step sending back the input given."""

    @step()
    async def run_step(self, ev: StartEvent) -> StopEvent:
        msg = str(ev.get("message", ""))
        f = Figlet(font="slant")
        ascii_art_message = f.renderText(msg)
        ascii_art_message += cow.Stegosaurus().milk(msg)
        return StopEvent(result=ascii_art_message)


echo_workflow = EchoWorkflow()


async def main():
    print(await echo_workflow.run(message="Hello!"))


if __name__ == "__main__":
    asyncio.run(main())
