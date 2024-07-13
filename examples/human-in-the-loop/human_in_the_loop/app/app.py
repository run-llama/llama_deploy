"""Gradio app."""

from io import StringIO
from typing import Any, List, Tuple
import gradio as gr
import sys

FALLBACK_PROMPT_PARAMS = {"message": "No prompt params provided."}


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
    app: gr.Blocks

    def __init__(self) -> None:
        self.app = gr.Blocks()

        with self.app:
            with gr.Row():
                gr.Markdown("# Human In The Loop")
            with gr.Row():
                chat_window = gr.Chatbot(
                    label="Message History",
                    scale=3,
                )
                console = gr.HTML(elem_id="box")
            with gr.Row():
                message = gr.Textbox(label="Write A Message", scale=4)
                clear = gr.ClearButton()

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
            clear.click(self._reset_chat, None, [message, chat_window, console])

    def _handle_user_message(
        self, user_message: str, chat_history: List[List[Tuple[str, str]]]
    ) -> Tuple[str, List[List[Tuple[str, str]]]]:
        """Handle the user submitted message. Clear message box, and append
        to the history.
        """
        return "", [*chat_history, [(user_message, "")]]
        ...

    def _generate_response(self, chat_history: List[List[Tuple[str, str]]]):
        with Capturing() as output:
            response = self.agent.stream_chat(chat_history[-1][0])
            ansi = "\n========\n".join(output)
            html_output = self.conv.convert(ansi)
            for token in response.response_gen:
                chat_history[-1][1] += token
                yield chat_history, str(html_output)

    def _reset_chat(self) -> Tuple[str, str, str]:
        return "", "", ""  # clear textboxes


if __name__ == "__main__":
    app = HumanInTheLoopGradioApp().app
    app.launch(server_name="0.0.0.0", server_port=8080)
