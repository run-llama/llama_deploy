from typing import Any, Dict, List, Tuple

from llama_index.core.llms import LLM
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.tools import BaseTool

from llama_agents.messages.base import QueueMessage
from llama_agents.orchestrators.base import BaseOrchestrator
from llama_agents.tools.service_tool import ServiceTool
from llama_agents.types import ActionTypes, ChatMessage, TaskDefinition, TaskResult

import logging

logger = logging.getLogger(__name__)

HISTORY_KEY = "chat_history"
RESULT_KEY = "result"
DEFAULT_SUMMARIZE_TMPL = "{history}\n\nThe above represents the progress so far, please condense the messages into a single message."
DEFAULT_FOLLOWUP_TMPL = (
    "Pick the next action to take. Invoke the 'finalize' tool with your full final answer if the answer to the original input is in the chat history. "
    "As a reminder, the original input was: {original_input}"
)


class AgentOrchestrator(BaseOrchestrator):
    def __init__(
        self,
        llm: LLM,
        human_description: str = "Useful for finalizing a response. Should contain a complete answer to the original input.",
        summarize_prompt: str = DEFAULT_SUMMARIZE_TMPL,
        followup_prompt: str = DEFAULT_FOLLOWUP_TMPL,
    ):
        self.llm = llm
        self.summarize_prompt = summarize_prompt
        self.followup_prompt = followup_prompt
        self.finalize_tool = ServiceTool(name="finalize", description=human_description)

    async def get_next_messages(
        self, task_def: TaskDefinition, tools: List[BaseTool], state: Dict[str, Any]
    ) -> Tuple[List[QueueMessage], Dict[str, Any]]:
        tools_plus_human = [self.finalize_tool, *tools]

        chat_dicts = state.get(HISTORY_KEY, [])
        chat_history = [ChatMessage(**x) for x in chat_dicts]

        # TODO: how to make memory configurable?
        memory = ChatMemoryBuffer.from_defaults(chat_history=chat_history, llm=self.llm)

        # check if first message
        if len(chat_history) == 0:
            logger.debug("Agent input: " + task_def.input)
            memory.put(ChatMessage(role="user", content=task_def.input))
            response = await self.llm.apredict_and_call(
                tools,
                user_msg=task_def.input,
                error_on_no_tool_call=False,
            )
        else:
            messages = memory.get()
            logger.debug("Agent input: " + str(messages))
            response = await self.llm.apredict_and_call(
                tools_plus_human,
                chat_history=messages,
                error_on_no_tool_call=False,
            )

        # check if there was a tool call
        queue_messages = []
        result = None
        logger.debug(f"Agent response sources: {response.sources}")
        if len(response.sources) == 0 or response.sources[0].tool_name == "finalize":
            # convert memory chat messages
            llama_messages = memory.get_all()
            history = [ChatMessage(**x.dict()) for x in llama_messages]

            result = TaskResult(
                task_id=task_def.task_id, history=history, result=response.response
            )

            queue_messages.append(
                QueueMessage(
                    type="human",
                    data=result.model_dump(),
                    action=ActionTypes.COMPLETED_TASK,
                )
            )
        else:
            for source in response.sources:
                name = source.tool_name
                input_data = source.raw_input
                input_str = next(iter(input_data.values()))
                queue_messages.append(
                    QueueMessage(
                        type=name,
                        data=TaskDefinition(
                            task_id=task_def.task_id, input=input_str
                        ).model_dump(),
                        action=ActionTypes.NEW_TASK,
                    )
                )

        new_state = {
            HISTORY_KEY: [x.dict() for x in memory.get_all()],
            RESULT_KEY: result.model_dump() if result is not None else None,
        }
        return queue_messages, new_state

    async def add_result_to_state(
        self,
        result: TaskResult,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Add the result of processing a message to the state. Returns the new state."""

        # summarize the result
        new_history = result.history
        new_history_str = "\n".join([str(x) for x in new_history])
        # TODO: Better logic for when to summarize?
        if len(new_history) > 1:
            summarize_prompt_str = self.summarize_prompt.format(history=new_history_str)
            summary = await self.llm.acomplete(summarize_prompt_str)

        # get the current chat history, add the summary to it
        chat_dicts = state.get(HISTORY_KEY, [])
        chat_history = [ChatMessage(**x) for x in chat_dicts]

        chat_history.append(ChatMessage(role="assistant", content=str(summary)))

        # add the followup prompt to the chat history
        original_input = chat_history[0].content
        chat_history.append(
            ChatMessage(
                role="user",
                content=self.followup_prompt.format(original_input=original_input),
            )
        )

        new_state = {HISTORY_KEY: [x.dict() for x in chat_history]}
        return new_state
