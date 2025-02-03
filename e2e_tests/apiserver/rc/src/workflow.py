import asyncio

from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)


class Message(Event):
    text: str


class EchoWorkflow(Workflow):
    """A dummy workflow streaming three events."""

    @step()
    async def run_step(self, ctx: Context, ev: StartEvent) -> StopEvent:
        for i in range(3):
            ctx.write_event_to_stream(Message(text=f"message number {i + 1}"))
            await asyncio.sleep(0.5)

        return StopEvent(result="Done.")


echo_workflow = EchoWorkflow()


async def main():
    h = echo_workflow.run(message="Hello!")
    async for ev in h.stream_events():
        if type(ev) is Message:
            print(ev.text)
    print(await h)


if __name__ == "__main__":
    asyncio.run(main())
