import pytest
from typing import Any, List, Optional, Union

from llama_index.core.chat_engine.types import AgentChatResponse
from llama_index.core.tools.types import BaseTool, ToolOutput
from llama_index.core.llms import (
    CustomLLM,
    CompletionResponse,
    CompletionResponseGen,
    LLMMetadata,
)

from llama_agents.orchestrators.agent import AgentOrchestrator
from llama_agents.messages.base import QueueMessage
from llama_agents.orchestrators.service_tool import ServiceTool
from llama_agents.types import ActionTypes, ChatMessage, TaskDefinition, TaskResult

TASK_DEF = TaskDefinition(
    input="Tell me a secret fact.",
    state={},
)

TOOLS = [
    ServiceTool(
        "secret_fact_agent",
        "Knows the secret fact",
    ),
    ServiceTool("dumb_fact_agent", "Knows only dumb facts"),
]

INITIAL_QUEUE_MESSAGE = QueueMessage(
    type="secret_fact_agent",
    data=TaskDefinition(input="What is the secret fact?").model_dump(),
    action=ActionTypes.NEW_TASK,
)


class MockOrchestratorLLM(CustomLLM):
    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata()

    def complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponse:
        return CompletionResponse(text=prompt)

    def stream_complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponseGen:
        pass

    async def apredict_and_call(
        self,
        tools: List[BaseTool],
        user_msg: Optional[Union[str, ChatMessage]] = None,
        chat_history: Optional[List[ChatMessage]] = None,
        verbose: bool = False,
        **kwargs: Any
    ) -> AgentChatResponse:
        if user_msg == "Tell me a secret fact.":
            return AgentChatResponse(
                response="",
                sources=[
                    ToolOutput(
                        content="fake",
                        tool_name="secret_fact_agent",
                        raw_input={"input": "What is the secret fact?"},
                    )
                ],
            )
        else:
            raise ValueError("Unsupported input.")


@pytest.mark.asyncio()
async def test_get_next_message() -> None:
    orchestrator = AgentOrchestrator(llm=MockOrchestratorLLM())

    queue_messages, state = await orchestrator.get_next_messages(
        TASK_DEF,
        TOOLS,
        TASK_DEF.state,
    )

    assert len(queue_messages) == 1
    assert queue_messages[0].type == TOOLS[0].name
    assert isinstance(queue_messages[0].data, dict)
    assert queue_messages[0].data["input"] == INITIAL_QUEUE_MESSAGE.data["input"]  # type: ignore

    assert "chat_history" in state
    assert isinstance(state["chat_history"], list)
    assert len(state["chat_history"]) == 1

    chat_dict = state["chat_history"][0]
    assert chat_dict["role"] == "user"
    assert chat_dict["content"] == TASK_DEF.input


@pytest.mark.asyncio()
async def test_add_result_to_state() -> None:
    orchestrator = AgentOrchestrator(llm=MockOrchestratorLLM())

    _, state = await orchestrator.get_next_messages(
        TASK_DEF,
        TOOLS,
        TASK_DEF.state,
    )

    new_state = await orchestrator.add_result_to_state(
        TaskResult(
            task_id=TASK_DEF.task_id,
            result="The secret fact is: A Cria is a baby llama.",
            history=[
                ChatMessage(role="user", content="What is the secret fact?"),
                ChatMessage(
                    role="assistant",
                    content="The secret fact is: A Cria is a baby llama.",
                ),
            ],
        ),
        state,
    )

    assert "chat_history" in new_state
    assert isinstance(new_state["chat_history"], list)
    assert len(new_state["chat_history"]) == 3

    # check if the summary prompt was used
    assert "condense the messages" in new_state["chat_history"][1]["content"]

    # check if the followup prompt was used
    assert "Pick the next action" in new_state["chat_history"][2]["content"]
