import asyncio

from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step
from llama_index.llms.openai import OpenAI


# create a dummy workflow
class EchoWorkflow(Workflow):
    """A dummy workflow with only one step sending back the input given."""

    llm: OpenAI = OpenAI(model="gpt-4.1-nano")

    @step()
    async def run_step(self, ev: StartEvent) -> StopEvent:
        message = str(ev.get("message", ""))
        response = await self.llm.acomplete(message)
        return StopEvent(result=response.text)


workflow = EchoWorkflow()


async def main() -> None:
    print(await workflow.run(message="Hello!"))


if __name__ == "__main__":
    asyncio.run(main())
