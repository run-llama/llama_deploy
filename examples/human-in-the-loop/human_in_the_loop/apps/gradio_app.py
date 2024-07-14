"""Gradio app."""

from io import StringIO
from typing import Any, List, Optional, Tuple
import asyncio
import gradio as gr
import sys

from llama_agents import LlamaAgentsClient
from human_in_the_loop.apps.css import css

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Capturing(list):
    """To capture the stdout from `BaseAgent.stream_chat` with `verbose=True`. Taken from
    https://stackoverflow.com/questions/16571150/\
        how-to-capture-stdout-output-from-a-python-function-call.
    """

    def __enter__(self) -> Any:
        self._stdout = sys.stdout
        sys.stdout = self._stringio = StringIO()
        return self

    def __exit__(self, *args) -> None:
        self.extend(self._stringio.getvalue().splitlines())
        del self._stringio  # free up some memory
        sys.stdout = self._stdout


class HumanInTheLoopGradioApp:
    """Human In The Loop Gradio App."""

    def __init__(
        self,
        human_in_loop_queue: asyncio.Queue,
        human_in_loop_result_queue: asyncio.Queue,
        control_plane_host: str = "127.0.0.1",
        control_plane_port: Optional[int] = 8000,
    ) -> None:
        self.human_in_loop_queue = human_in_loop_queue
        logger.info(f"{human_in_loop_queue.empty()}")
        self.app = gr.Blocks(css=css)
        self._client = LlamaAgentsClient(
            control_plane_url=(
                f"http://{control_plane_host}:{control_plane_port}"
                if control_plane_port
                else f"http://{control_plane_host}"
            )
        )
        self._step_interval = 0.5
        self._timeout = 60
        self._raise_timeout = False
        self._human_in_the_loop_task: Optional[str] = None
        self._human_input: Optional[str] = None

        with self.app:
            with gr.Row():
                gr.Markdown("# Human In The Loop")
            with gr.Row():
                chat_window = gr.Chatbot(
                    type="messages",
                    label="Message History",
                    scale=3,
                )
                console = gr.HTML(elem_id="box")
            with gr.Row():
                message = gr.Textbox(label="Write A Message", scale=4)
                clear = gr.ClearButton()
            with gr.Row():
                human_prompt = gr.Textbox(label="Human Prompt")
            with gr.Row():
                with gr.Column():
                    philosophy_quotes = [
                        ["I think therefore I am."],
                        ["The unexamined life is not worth living."],
                    ]
                    markdown = gr.Markdown(visible=False)
                    dataset = gr.Dataset(
                        components=[markdown],
                        samples=philosophy_quotes,
                        label="Human Input Required",
                        elem_classes="human-needed",
                    )
                with gr.Column():
                    philosophy_quotes = [
                        ["I think therefore I am."],
                        ["The unexamined life is not worth living."],
                    ]
                    markdown = gr.Markdown(visible=False)
                    dataset = gr.Dataset(
                        components=[markdown],
                        samples=philosophy_quotes,
                        label="Completed Tasks",
                        elem_classes="completed-tasks",
                    )
            timer = gr.Timer(2)

            # event listeners
            # message submit
            message.submit(
                self._handle_user_message,
                [message, chat_window],
                [message, chat_window],
                queue=False,
            ).then(
                self._generate_response,
                chat_window,
                [chat_window, console],
            )
            # tick
            timer.tick(self._tick_handler, [], human_prompt, queue=True)

            # clear chat
            clear.click(self._reset_chat, None, [message, chat_window, console])

    async def _tick_handler(
        self,
    ) -> str:
        logger.info("tick_handler")
        try:
            prompt = self.human_in_loop_queue.get_nowait()
            logger.info("appended human input request.")
        except asyncio.QueueEmpty:
            logger.info("human input request queue is empty.")
            pass
            prompt = ""

        return prompt

    async def _handle_user_message(
        self, user_message: str, chat_history: List[Tuple[str, str]]
    ) -> Tuple[str, List[Tuple[str, str]]]:
        """Handle the user submitted message. Clear message box, and append
        to the history.
        """
        if self._human_in_the_loop_task:
            self._human_input = user_message
        message = gr.ChatMessage(role="user", content=user_message)
        chat_history.append(message)
        return "", chat_history

    async def _poll_for_task_result(self, task_id: str):
        task_result = None
        while task_result is None:
            if not self.human_in_loop_queue.empty():
                break
            try:
                task_result = self._client.get_task_result(task_id)
            except Exception:
                pass
            await asyncio.sleep(1)
        return task_result

    async def _generate_response(self, chat_history: List[gr.ChatMessage]):
        user_message = gr.ChatMessage(**chat_history[-1])
        task_id = self._client.create_task(user_message.content)
        message = gr.ChatMessage(
            role="assistant", content=f"Successfully submitted task: {task_id}."
        )
        chat_history.append(message)
        return chat_history, ""

        # # poll for tool_call_result with max timeout
        # try:
        #     task_result = await asyncio.wait_for(
        #         self._poll_for_task_result(task_id=task_id),
        #         timeout=self._timeout,
        #     )
        # except (
        #     asyncio.exceptions.TimeoutError,
        #     asyncio.TimeoutError,
        #     TimeoutError,
        # ) as e:
        #     logger.debug(f"Timeout reached for task with id {task_id}")
        #     if self._raise_timeout:
        #         raise
        #     task_result = TaskResult(
        #         task_id=task_id,
        #         result="Encountered error: " + str(e),
        #         history=[],
        #         data={"error": str(e)},
        #     )

        # # update assistant message
        # assistant_message = gr.ChatMessage(role="assistant", content=task_result.result)
        # chat_history.append(assistant_message)

        # return chat_history, ""

    def _reset_chat(self) -> Tuple[str, str, str]:
        return "", "", ""  # clear textboxes


app = HumanInTheLoopGradioApp(asyncio.Queue(), asyncio.Queue()).app

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=8080)
