import re
import time
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel

from llama_index.core.chat_engine.types import ChatMessage
from llama_index.core.llms import LLM
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.prompts import PromptTemplate
from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
from llama_index.server.api.utils import get_last_artifact
from llama_index.server.models import (
    Artifact,
    ArtifactEvent,
    ArtifactType,
    ChatRequest,
    CodeArtifactData,
    UIEvent,
)
from llama_index.llms.openai import OpenAI


class Requirement(BaseModel):
    next_step: Literal["answering", "coding"]
    language: Optional[str] = None
    file_name: Optional[str] = None
    requirement: str


class PlanEvent(Event):
    user_msg: str
    context: Optional[str] = None


class GenerateArtifactEvent(Event):
    requirement: Requirement


class SynthesizeAnswerEvent(Event):
    pass


class UIEventData(BaseModel):
    state: Literal["plan", "generate", "completed"]
    requirement: Optional[str] = None


class ArtifactWorkflow(Workflow):
    """
    A simple workflow that help generate/update the chat artifact (code, document)
    e.g: Help create a NextJS app.
         Update the generated code with the user's feedback.
         Generate a guideline for the app,...
    """

    def __init__(
        self,
        llm: LLM,
        chat_request: ChatRequest,
        **kwargs: Any,
    ):
        """
        Args:
            llm: The LLM to use.
            chat_request: The chat request from the chat app to use.
        """
        super().__init__(**kwargs)
        self.llm = llm
        self.last_artifact = get_last_artifact(chat_request)

    @step
    async def prepare_chat_history(self, ctx: Context, ev: StartEvent) -> PlanEvent:
        user_msg = ev.user_msg
        if user_msg is None:
            raise ValueError("user_msg is required to run the workflow")
        await ctx.set("user_msg", user_msg)
        chat_history = ev.chat_history or []
        chat_history.append(
            ChatMessage(
                role="user",
                content=user_msg,
            )
        )
        memory = ChatMemoryBuffer.from_defaults(
            chat_history=chat_history,
            llm=self.llm,
        )
        await ctx.set("memory", memory)
        return PlanEvent(
            user_msg=user_msg,
            context=str(self.last_artifact.model_dump_json())
            if self.last_artifact
            else "",
        )

    @step
    async def planning(
        self, ctx: Context, event: PlanEvent
    ) -> Union[GenerateArtifactEvent, SynthesizeAnswerEvent]:
        """
        Based on the conversation history and the user's request
        this step will help to provide a good next step for the code or document generation.
        """
        ctx.write_event_to_stream(
            UIEvent(
                type="ui_event",
                data=UIEventData(
                    state="plan",
                    requirement=None,
                ),
            )
        )
        prompt = PromptTemplate("""
        You are a product analyst responsible for analyzing the user's request and providing the next step for code or document generation.
        You are helping user with their code artifact. To update the code, you need to plan a coding step.
    
        Follow these instructions:
        1. Carefully analyze the conversation history and the user's request to determine what has been done and what the next step should be.
        2. The next step must be one of the following two options:
           - "coding": To make the changes to the current code.
           - "answering": If you don't need to update the current code or need clarification from the user.
        Important: Avoid telling the user to update the code themselves, you are the one who will update the code (by planning a coding step).
        3. If the next step is "coding", you may specify the language ("typescript" or "python") and file_name if known, otherwise set them to null. 
        4. The requirement must be provided clearly what is the user request and what need to be done for the next step in details
           as precise and specific as possible, don't be stingy with in the requirement.
        5. If the next step is "answering", set language and file_name to null, and the requirement should describe what to answer or explain to the user.
        6. Be concise; only return the requirements for the next step.
        7. The requirements must be in the following format:
           ```json
           {
               "next_step": "answering" | "coding",
               "language": "typescript" | "python" | null,
               "file_name": string | null,
               "requirement": string
           }
           ```

        ## Example 1:
        User request: Create a calculator app.
        You should return:
        ```json
        {
            "next_step": "coding",
            "language": "typescript",
            "file_name": "calculator.tsx",
            "requirement": "Generate code for a calculator app that has a simple UI with a display and button layout. The display should show the current input and the result. The buttons should include basic operators, numbers, clear, and equals. The calculation should work correctly."
        }
        ```

        ## Example 2:
        User request: Explain how the game loop works.
        Context: You have already generated the code for a snake game.
        You should return:
        ```json
        {
            "next_step": "answering",
            "language": null,
            "file_name": null,
            "requirement": "The user is asking about the game loop. Explain how the game loop works."
        }
        ```

        {context}

        Now, plan the user's next step for this request:
        {user_msg}
        """).format(
            context=""
            if event.context is None
            else f"## The context is: \n{event.context}\n",
            user_msg=event.user_msg,
        )
        response = await self.llm.acomplete(
            prompt=prompt,
            formatted=True,
        )
        # parse the response to Requirement
        # 1. use regex to find the json block
        json_block = re.search(
            r"```(?:json)?\s*([\s\S]*?)\s*```", response.text, re.IGNORECASE
        )
        if json_block is None:
            raise ValueError("No JSON block found in the response.")
        # 2. parse the json block to Requirement
        requirement = Requirement.model_validate_json(json_block.group(1).strip())
        ctx.write_event_to_stream(
            UIEvent(
                type="ui_event",
                data=UIEventData(
                    state="generate",
                    requirement=requirement.requirement,
                ),
            )
        )
        # Put the planning result to the memory
        # useful for answering step
        memory: ChatMemoryBuffer = await ctx.get("memory")
        memory.put(
            ChatMessage(
                role="assistant",
                content=f"The plan for next step: \n{response.text}",
            )
        )
        await ctx.set("memory", memory)
        if requirement.next_step == "coding":
            return GenerateArtifactEvent(
                requirement=requirement,
            )
        else:
            return SynthesizeAnswerEvent()

    @step
    async def generate_artifact(
        self, ctx: Context, event: GenerateArtifactEvent
    ) -> SynthesizeAnswerEvent:
        """
        Generate the code based on the user's request.
        """
        ctx.write_event_to_stream(
            UIEvent(
                type="ui_event",
                data=UIEventData(
                    state="generate",
                    requirement=event.requirement.requirement,
                ),
            )
        )
        prompt = PromptTemplate("""
         You are a skilled developer who can help user with coding.
         You are given a task to generate or update a code for a given requirement.

         ## Follow these instructions:
         **1. Carefully read the user's requirements.** 
            If any details are ambiguous or missing, make reasonable assumptions and clearly reflect those in your output.
            If the previous code is provided:
            + Carefully analyze the code with the request to make the right changes.
            + Avoid making a lot of changes from the previous code if the request is not to write the code from scratch again.
         **2. For code requests:**
            - If the user does not specify a framework or language, default to a React component using the Next.js framework.
            - For Next.js, use Shadcn UI components, Typescript, @types/node, @types/react, @types/react-dom, PostCSS, and TailwindCSS.
            The import pattern should be:
            ```
            import { ComponentName } from "@/components/ui/component-name"
            import { Markdown } from "@llamaindex/chat-ui"
            import { cn } from "@/lib/utils"
            ```
            - Ensure the code is idiomatic, production-ready, and includes necessary imports.
            - Only generate code relevant to the user's request—do not add extra boilerplate.
         **3. Don't be verbose on response**
            - No other text or comments only return the code which wrapped by ```language``` block.
            - If the user's request is to update the code, only return the updated code.
         **4. Only the following languages are allowed: "typescript", "python".**
         **5. If there is no code to update, return the reason without any code block.**
            
         ## Example:
         ```typescript
         import React from "react";
         import { Button } from "@/components/ui/button";
         import { cn } from "@/lib/utils";

         export default function MyComponent() {
         return (
            <div className="flex flex-col items-center justify-center h-screen">
               <Button>Click me</Button>
            </div>
         );
         }

         The previous code is:
         {previous_artifact}

         Now, i have to generate the code for the following requirement:
         {requirement}
         ```
        """).format(
            previous_artifact=self.last_artifact.model_dump_json()
            if self.last_artifact
            else "",
            requirement=event.requirement,
        )
        response = await self.llm.acomplete(
            prompt=prompt,
            formatted=True,
        )
        # Extract the code from the response
        language_pattern = r"```(\w+)([\s\S]*)```"
        code_match = re.search(language_pattern, response.text)
        if code_match is None:
            return SynthesizeAnswerEvent()
        else:
            code = code_match.group(2).strip()
        # Put the generated code to the memory
        memory: ChatMemoryBuffer = await ctx.get("memory")
        memory.put(
            ChatMessage(
                role="assistant",
                content=f"Updated the code: \n{response.text}",
            )
        )
        # To show the Canvas panel for the artifact
        ctx.write_event_to_stream(
            ArtifactEvent(
                data=Artifact(
                    type=ArtifactType.CODE,
                    created_at=int(time.time()),
                    data=CodeArtifactData(
                        language=event.requirement.language or "",
                        file_name=event.requirement.file_name or "",
                        code=code,
                    ),
                ),
            )
        )
        return SynthesizeAnswerEvent()

    @step
    async def synthesize_answer(
        self, ctx: Context, event: SynthesizeAnswerEvent
    ) -> StopEvent:
        """
        Synthesize the answer.
        """
        memory: ChatMemoryBuffer = await ctx.get("memory")
        chat_history = memory.get()
        chat_history.append(
            ChatMessage(
                role="system",
                content="""
                You are a helpful assistant who is responsible for explaining the work to the user.
                Based on the conversation history, provide an answer to the user's question. 
                The user has access to the code so avoid mentioning the whole code again in your response.
                """,
            )
        )
        response_stream = await self.llm.astream_chat(
            messages=chat_history,
        )
        ctx.write_event_to_stream(
            UIEvent(
                type="ui_event",
                data=UIEventData(
                    state="completed",
                ),
            )
        )
        return StopEvent(result=response_stream)

code_artifact_workflow = ArtifactWorkflow(
    # TODO: how can we pass the data from the chat request to the workflow?
    # evaluate option to send the chat_request with the start event (instead of the chat_history) - this depends on the llama_deploy implementation
    llm=OpenAI(model="gpt-4o-mini"),
)
