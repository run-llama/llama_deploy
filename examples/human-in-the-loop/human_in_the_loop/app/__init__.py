"""Gradio app."""


import gradio as gr

FALLBACK_PROMPT_PARAMS = {"message": "No prompt params provided."}


class HumanInTheLoopGradioApp:
    app: gr.Blocks

    def __init__(self) -> None:
        self.app = gr.Blocks()

        with self.app:
            with gr.Row():
                gr.Markdown("# Human In The Loop")
            ...


if __name__ == "__main__":
    app = HumanInTheLoopGradioApp().app
    app.launch(server_name="0.0.0.0", server_port=8080)
