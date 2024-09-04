from typing import List

from llama_index.core.llms import ChatMessage
from llama_index.core.memory import ChatSummaryMemoryBuffer
from llama_index.core.workflow import Event, Workflow, StartEvent, StopEvent, step
from llama_index.llms.openai import OpenAI
from llama_index.core.tools import FunctionTool

from rag_workflow import RAGWorkflow


class ChatEvent(Event):
    chat_history: List[ChatMessage]


class AgenticWorkflow(Workflow):
    llm: OpenAI = OpenAI(model="gpt-4o")

    @step
    def prepare_chat_history(self, ev: StartEvent) -> ChatEvent:
        chat_history_dicts = ev.get("chat_history_dicts", [])
        chat_history = [
            ChatMessage(**chat_history_dict) for chat_history_dict in chat_history_dicts
        ]

        newest_msg = ev.get("user_input")
        if not newest_msg:
            raise ValueError("No `user_input` input provided!")

        chat_history.append(ChatMessage(role="user", content=newest_msg))

        memory = ChatSummaryMemoryBuffer.from_defaults(
            chat_history=chat_history,
            llm=OpenAI(model="gpt-4o-mini"),
        )

        processed_chat_history = memory.get()

        return ChatEvent(chat_history=processed_chat_history)

    @step
    async def chat(self, ev: ChatEvent, rag_workflow: RAGWorkflow) -> StopEvent:
        chat_history = ev.get("chat_history")

        async def run_query(query: str) -> str:
            """Useful for running a natural language query against a knowledge base."""
            response = await rag_workflow.run(query=query)
            return response["response"]

        tool = FunctionTool.from_defaults(async_fn=run_query)

        # responds using the tool or the LLM directly
        response = await self.llm.apredict_and_call(
            [tool],
            chat_history=chat_history,
        )

        return StopEvent(response=response.response)


def build_agentic_workflow(rag_workflow: RAGWorkflow) -> AgenticWorkflow:
    agentic_workflow = AgenticWorkflow()

    # add the rag workflow as a subworkflow
    agentic_workflow.add_workflows(rag_workflow=rag_workflow)

    return agentic_workflow
