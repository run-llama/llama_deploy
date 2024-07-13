"""Gradio app."""

from io import StringIO
from typing import Any, List, Optional, Tuple, Literal
import asyncio
import gradio as gr
from logging import getLogger
import sys

from llama_agents import LlamaAgentsClient, HumanService
from llama_agents.types import TaskResult

from human_in_the_loop.utils import load_from_env
from human_in_the_loop.additional_services.human_in_the_loop import (
    human_service,
    launch as human_service_launch,
)

control_plane_host = load_from_env("CONTROL_PLANE_HOST")
control_plane_port = load_from_env("CONTROL_PLANE_PORT")

logger = getLogger(__name__)


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
        human_in_the_loop_service: HumanService,
        control_plane_host: str = "127.0.0.1",
        control_plane_port: Optional[int] = 8000,
    ) -> None:
        self.app = gr.Blocks()
        self.human_in_the_loop_service = human_in_the_loop_service
        self._client = LlamaAgentsClient(
            control_plane_url=(
                f"http://{control_plane_host}:{control_plane_port}"
                if control_plane_port
                else f"http://{control_plane_host}"
            )
        )
        self._step_interval = 0.1
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
            timer = gr.Timer(0.1)

            # human in the loop
            async def human_input_fn(prompt: str, kwargs: Any) -> str:
                self._human_in_the_loop_task = prompt
                # poll until human answer is stored

                async def _poll_for_human_input_result():
                    while self._human_input is None:
                        await asyncio.sleep(self._step_interval)
                    return self._human_input

                human_input = await asyncio.wait_for(
                    self._poll_for_human_input_result(),
                    timeout=10,
                )

                # cleanup
                self._human_in_the_loop_task = None
                self._human_input = None

                return human_input

            self.human_in_the_loop_service.fn_input = human_input_fn

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
            timer.tick(self._tick_handler, chat_window, chat_window)

            # clear chat
            clear.click(self._reset_chat, None, [message, chat_window, console])

    async def _tick_handler(
        self, chat_history: List[gr.ChatMessage]
    ) -> List[gr.ChatMessage]:
        if self._human_in_the_loop_task:
            assistant_message = gr.ChatMessage(
                role="assistant",
                content=self._human_in_the_loop_task,
                metadata={"title": "Agent asking for human input."},
            )
            chat_history.append(assistant_message)
        return chat_history

    async def _handle_user_message(
        self, user_message: str, chat_history: List[Tuple[str, str]]
    ) -> Tuple[str, List[Tuple[str, str]]]:
        """Handle the user submitted message. Clear message box, and append
        to the history.
        """
        if self._human_in_the_loop_task:
            self._human_input = user_message
        message = gr.ChatMessage(role="user", content=user_message)
        return "", [*chat_history, message]

    async def _poll_for_task_result(self, task_id: str):
        task_result = None
        while task_result is None:
            try:
                task_result = self._client.get_task_result(task_id)
            except Exception:
                pass
            await asyncio.sleep(self._step_interval)
        return task_result

    async def _generate_response(self, chat_history: List[gr.ChatMessage]):
        user_message = gr.ChatMessage(**chat_history[-1])
        task_id = self._client.create_task(user_message.content)

        # poll for tool_call_result with max timeout
        try:
            task_result = await asyncio.wait_for(
                self._poll_for_tool_call_result(task_id=task_id),
                timeout=self._timeout,
            )
        except (
            asyncio.exceptions.TimeoutError,
            asyncio.TimeoutError,
            TimeoutError,
        ) as e:
            logger.debug(f"Timeout reached for task with id {task_id}")
            if self._raise_timeout:
                raise
            task_result = TaskResult(
                task_id=task_id,
                result="Encountered error: " + str(e),
                history=[],
                data={"error": str(e)},
            )

        # update assistant message
        assistant_message = gr.ChatMessage(role="assistant", content=task_result.result)
        chat_history.append(assistant_message)

        return chat_history, ""

    def _reset_chat(self) -> Tuple[str, str, str]:
        return "", "", ""  # clear textboxes


app = HumanInTheLoopGradioApp(
    human_in_the_loop_service=human_service,
    control_plane_host=control_plane_host,
    control_plane_port=control_plane_port,
).app

if __name__ == "__main__":
    _ = asyncio.create_task(human_service_launch())
    app.launch(server_name="0.0.0.0", server_port=8080)
