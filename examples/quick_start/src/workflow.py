import asyncio

from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step


# create a dummy workflow
class EchoWorkflow(Workflow):
    """A dummy workflow with only one step sending back the input given."""

    @step()
    async def run_step(self, ev: StartEvent) -> StopEvent:
        message = str(ev.get("message", ""))
        return StopEvent(result=f"Message received: {message}")


echo_workflow = EchoWorkflow()


async def main():
    print(await echo_workflow.run(message="Hello!"))


if __name__ == "__main__":
    asyncio.run(main())
