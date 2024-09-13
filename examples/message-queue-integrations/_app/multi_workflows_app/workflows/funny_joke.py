from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step
from llama_index.llms.openai import OpenAI


class FunnyJokeWorkflow(Workflow):
    @step
    async def add_funny_joke_step(self, ev: StartEvent) -> StopEvent:
        # Your workflow logic here
        input = str(ev.get("input", ""))
        llm = OpenAI("gpt-4o-mini", temperature=0.1)
        response = await llm.acomplete(
            "Tell a funny, light-hearted joke about " + input
        )
        result = "\n\nAnd here is a funny joke about " + input + ":\n\n" + response.text
        return StopEvent(result=result)


# Local Testing
async def _test_workflow():
    w = FunnyJokeWorkflow(timeout=60, verbose=False)
    result = await w.run(input="A baby llama is called a cria.")
    print(str(result))


if __name__ == "__main__":
    import asyncio

    asyncio.run(_test_workflow())
