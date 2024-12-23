from logging import getLogger
from typing import List

from llama_index.core.llms import ChatMessage
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.tools import FunctionTool
from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
from llama_index.llms.openai import OpenAI

from .rag_workflow import RAGWorkflow

logger = getLogger(__name__)


class ChatEvent(Event):
    chat_history: List[ChatMessage]


class AgenticWorkflow(Workflow):
    llm: OpenAI = OpenAI(model="gpt-4o")

    @step
    async def prepare_chat_history(self, ctx: Context, ev: StartEvent) -> ChatEvent:
        logger.info(f"Preparing chat history: {ev}")

        current_chat_history = await ctx.get("chat_history", [])

        newest_msg = ev.get("user_input")
        if not newest_msg:
            raise ValueError("No `user_input` input provided!")

        current_chat_history.append({"role": "user", "content": newest_msg})
        await ctx.set("chat_history", current_chat_history)

        memory = ChatMemoryBuffer.from_defaults(
            chat_history=[ChatMessage(**x) for x in current_chat_history],
            llm=OpenAI(model="gpt-4o-mini"),
        )

        processed_chat_history = memory.get()

        return ChatEvent(chat_history=processed_chat_history)

    @step
    async def chat(
        self, ctx: Context, ev: ChatEvent, rag_workflow: RAGWorkflow
    ) -> StopEvent:
        chat_history = ev.chat_history

        async def run_query(query: str) -> str:
            """
            Useful for running a natural language query against a general knowledge base containing the paper "Attention is all your need".
            If the user asks anything about a paper, use this tool to query it.
            The query input should be a senetence or question related to what the user wants.
            """
            response = await rag_workflow.run(query=query)
            return str(response)

        async def return_response(response: str) -> str:
            """Useful for returning a direct response to the user."""
            return response

        query_tool = FunctionTool.from_defaults(async_fn=run_query)
        response_tool = FunctionTool.from_defaults(async_fn=return_response)

        # responds using the tool or the LLM directly
        response = await self.llm.apredict_and_call(
            [query_tool, response_tool],
            chat_history=chat_history,
            error_on_no_tool_call=False,
        )

        # update the chat history in the context
        current_chat_history = await ctx.get("chat_history", [])
        current_chat_history.append({"role": "assistant", "content": response.response})
        await ctx.set("chat_history", current_chat_history)

        logger.info(f"Response: {response.response}")
        return StopEvent(result=response.response)


def build_agentic_workflow(rag_workflow: RAGWorkflow) -> AgenticWorkflow:
    agentic_workflow = AgenticWorkflow(timeout=120.0)

    # add the rag workflow as a subworkflow
    agentic_workflow.add_workflows(rag_workflow=rag_workflow)

    return agentic_workflow
