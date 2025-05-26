from llama_index.core.llms import ChatMessage
from llama_index.core.workflow import Context, Event, StartEvent, StopEvent, Workflow, step
from llama_index.llms.openai import OpenAI

class ChatEvent(StartEvent):
    messages: list[ChatMessage] | None = None
    message: str | None = None

class StreamEvent(Event):
    delta: str

class ResponseEvent(StopEvent):
    message: ChatMessage


class ChatWorkflow(Workflow):
    @step
    async def chat(self, ctx: Context, ev: ChatEvent) -> ResponseEvent:
        llm = OpenAI(model="gpt-4o-mini")
        if ev.messages:
            response_gen = await llm.astream_chat(ev.messages)
        elif ev.message:
            response_gen = await llm.astream_chat([ChatMessage(role="user", content=ev.message)])
        else:
            raise ValueError("No `messages` or `message` provided")

        full_resp = ChatMessage(role="assistant", content="")
        async for resp in response_gen:
            ctx.write_event_to_stream(StreamEvent(delta=resp.delta or ""))
            full_resp = resp.message
        
        return ResponseEvent(message=full_resp)

# Declare the workflow so that it is importable
workflow = ChatWorkflow()

# Some code to test the workflow with `python src/workflow.py`
async def main():
    handler = workflow.run(messages=[ChatMessage(role="user", content="Hello, how are you?")])
    async for event in handler:
        if isinstance(event, StreamEvent):
            print(event.delta, end="", flush=True)
    
    _ = await handler


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
        