import asyncio

from cowpy import cow
from fortune import fortune
from pydantic import Field
from pyfiglet import Figlet
from workflows import Workflow, step
from workflows.events import StartEvent, StopEvent


class CreateMessage(StartEvent):
    message: str = Field(
        description="A custom message to be displayed in the ascii art"
    )
    font: str = Field(
        default="blocky",
        description="The figlet ascii art font to use for the message. Some popular options are: blocky, standard, small, big, digital, banner, mini, etc.",
    )
    animal: str = Field(
        default="daemon",
        description="The animal/character to use for the ascii art. Options are: daemon, dragonandcow, stegosaurus, turtle, tux, vader, turkey, ghostbusters, surgery, kiss",
    )


class MessageCreated(StopEvent):
    rendered_message: str


# create a dummy workflow
class EchoWorkflow(Workflow):
    """A dummy workflow with only one step sending back the input given."""

    @step()
    async def run_step(self, ev: CreateMessage) -> MessageCreated:
        msg = str(ev.message)
        font = str(ev.font)
        animal = str(ev.animal)

        fortune_msg = fortune()
        f = Figlet(font=font)
        ascii_art_message = f.renderText(msg)

        # Get the selected cow character dynamically
        selected_cow = cow.get_cow(animal)
        ascii_art_message += selected_cow().milk(fortune_msg)

        return MessageCreated(rendered_message=ascii_art_message)


echo_workflow = EchoWorkflow()


async def main():
    print(await echo_workflow.run(message="Hello!", animal="daemon"))


if __name__ == "__main__":
    asyncio.run(main())
