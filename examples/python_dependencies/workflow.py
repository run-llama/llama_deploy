import asyncio

from cowpy import cow
from fortune import fortune
from pyfiglet import Figlet
from workflows import Workflow, step
from workflows.events import StartEvent, StopEvent


# create a dummy workflow
class EchoWorkflow(Workflow):
    """A dummy workflow with only one step sending back the input given."""

    @step()
    async def run_step(self, ev: StartEvent) -> StopEvent:
        msg = str(ev.get("message", ""))
        font = str(ev.get("font", "blocky"))
        fortune_msg = fortune()
        f = Figlet(font=font)
        ascii_art_message = f.renderText(msg)
        ascii_art_message += cow.Stegosaurus().milk(fortune_msg)
        return StopEvent(result=ascii_art_message)


echo_workflow = EchoWorkflow()


async def main():
    print(await echo_workflow.run(message="Hello!"))


if __name__ == "__main__":
    asyncio.run(main())
