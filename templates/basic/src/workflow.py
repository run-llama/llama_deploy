import asyncio

from llama_index.llms.openai import OpenAI
from workflows import Workflow, step
from workflows.events import StartEvent, StopEvent


# create a completion workflow
class CompletionWorkflow(Workflow):
    """A completion workflow with a single step."""

    llm: OpenAI = OpenAI(model="gpt-4.1-nano")

    @step()
    async def run_step(self, ev: StartEvent) -> StopEvent:
        message = str(ev.get("message", ""))
        response = await self.llm.acomplete(message)
        return StopEvent(result=response.text)


workflow = CompletionWorkflow()


async def main() -> None:
    print(await workflow.run(message="Hello!"))


if __name__ == "__main__":
    asyncio.run(main())
