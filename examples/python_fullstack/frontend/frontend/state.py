import asyncio
import json
import os
import uuid

import httpx
import reflex as rx


class State(rx.State):
    # The current question being asked.
    question: str

    # Keep track of the chat history as a list of question->answer sequences.
    # This is just a cache, the actual chat history is stored in the session state on the server.
    # When the session changes, this is replaced with the new session's chat history.
    chat_history: list[str] = []

    user_id: str = str(uuid.uuid4())

    async def get_remote_chat_history(self, session_id: str) -> list[str]:
        client = httpx.AsyncClient()

        deployment_name = os.environ.get("DEPLOYMENT_NAME", "MyDeployment")
        apiserver_url = os.environ.get("APISERVER_URL", "http://localhost:4501")
        response = await client.get(
            f"{apiserver_url}/deployments/{deployment_name}/sessions/{session_id}"
        )
        data = response.json()

        # need to pull the chat history from the context in the session state
        workflow_state = json.loads(data["state"].get(session_id, "{}"))
        chat_history = json.loads(
            workflow_state.get("state", {}).get("globals", {}).get("chat_history", "[]")
        )

        # convert to strings
        chat_history_strings = [x["content"] for x in chat_history]

        return chat_history_strings

    async def update_chat_history(self, session_id: str):
        if session_id:
            self.chat_history = await self.get_remote_chat_history(session_id)

    async def answer(self, session_id: str):
        # add the user's question to the chat history cache
        self.chat_history.append(self.question)

        # Clear the question input.
        question = self.question
        self.question = ""

        # Yield here to clear the frontend input before continuing.
        yield

        client = httpx.AsyncClient()

        # call the agentic workflow
        input_payload = {
            "user_input": question,
        }
        deployment_name = os.environ.get("DEPLOYMENT_NAME", "MyDeployment")
        apiserver_url = os.environ.get("APISERVER_URL", "http://localhost:4501")
        response = await client.post(
            f"{apiserver_url}/deployments/{deployment_name}/tasks/run?session_id={session_id}",
            json={"input": json.dumps(input_payload)},
            timeout=60,
        )
        answer = response.text

        self.chat_history.append("")

        for i in range(len(answer)):
            # Pause to show the streaming effect.
            await asyncio.sleep(0.01)
            # Add one letter at a time to the output.
            self.chat_history[-1] = answer[: i + 1]
            yield

    async def handle_key_down(self, key: str, session_id: str):
        if key == "Enter":
            async for t in self.answer(session_id):
                yield t
