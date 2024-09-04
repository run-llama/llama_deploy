import asyncio
import reflex as rx


class State(rx.State):
    # The current question being asked.
    question: str

    # Keep track of the chat history as a list of (question, answer) tuples.
    chat_history: list[tuple[str, str]]

    async def answer(self):
        # Our chatbot is not very smart right now...
        answer = "I don't know!"
        self.chat_history.append((self.question, ""))

        # Clear the question input.
        self.question = ""
        # Yield here to clear the frontend input before continuing.
        yield

        for i in range(len(answer)):
            # Pause to show the streaming effect.
            await asyncio.sleep(0.05)
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
