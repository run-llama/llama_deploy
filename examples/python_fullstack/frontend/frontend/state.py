import asyncio
import json
import os
import uuid

import httpx
import reflex as rx


class State(rx.State):
    # The current question being asked.
    question: str

    # Keep track of the chat history as a list of (question, answer) tuples.
    chat_history: list[tuple[str, str]]

    user_id: str = str(uuid.uuid4())

    async def answer(self):
        # convert chat history to a list of dictionaries
        chat_history_dicts = []
        for chat_history_tuple in self.chat_history:
            chat_history_dicts.append(
                {"role": "user", "content": chat_history_tuple[0]}
            )
            chat_history_dicts.append(
                {"role": "assistant", "content": chat_history_tuple[1]}
            )

        self.chat_history.append((self.question, ""))

        # Clear the question input.
        question = self.question
        self.question = ""

        # Yield here to clear the frontend input before continuing.
        yield

        client = httpx.AsyncClient()

        # call the agentic workflow
        input_payload = {
            "chat_history_dicts": chat_history_dicts,
            "user_input": question,
        }
        deployment_name = os.environ.get("DEPLOYMENT_NAME", "MyDeployment")
        apiserver_url = os.environ.get("APISERVER_URL", "http://localhost:4501")
        response = await client.post(
            f"{apiserver_url}/deployments/{deployment_name}/tasks/create",
            json={"input": json.dumps(input_payload)},
            timeout=60,
        )
        answer = response.text

        for i in range(len(answer)):
            # Pause to show the streaming effect.
            await asyncio.sleep(0.01)
            # Add one letter at a time to the output.
            self.chat_history[-1] = (
                self.chat_history[-1][0],
                answer[: i + 1],
            )
            yield

    async def handle_key_down(self, key: str):
        if key == "Enter":
            async for t in self.answer():
                yield t
