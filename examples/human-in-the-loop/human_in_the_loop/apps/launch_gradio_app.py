from human_in_the_loop.apps.gradio_app import gradio_app


app = gradio_app.app

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=8080)
