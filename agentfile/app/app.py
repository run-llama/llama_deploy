from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, Header, Footer, Static, Input


class ServiceButton(Button):
    pass


class TaskButton(Button):
    pass


class SimpleServerApp(App):
    CSS = """
    Screen {
        layout: grid;
        grid-size: 2;
        grid-columns: 1fr 2fr;
        padding: 0;
    }

    #left-panel {
        width: 100%;
        height: 100%;
    }

    #right-panel {
        width: 100%;
        height: 100%;
    }

    .section {
        background: $panel;
        padding: 1;
        margin-bottom: 0;
    }

    VerticalScroll {
        height: auto;
        max-height: 50%;
        border: solid $primary;
        margin-bottom: 1;
    }

    Button {
        width: 100%;
        margin-bottom: 1;
    }

    #details {
        height: 100%;
        background: $boost;
        padding: 1;
        text-align: center;
    }

    #new-task {
        dock: bottom;
        margin-bottom: 1;
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Static(id="left-panel"):
            # yield Static("Services", classes="section")
            with VerticalScroll():
                yield ServiceButton("Service 1")
                yield ServiceButton("Service 2")
                yield ServiceButton("Service 3")
            # yield Static("Tasks", classes="section")
            with VerticalScroll():
                yield TaskButton("Task 1")
                yield TaskButton("Task 2")
        with Static(id="right-panel"):
            yield Static("Task or service details", id="details")
        yield Input(placeholder="Enter: New task", id="new-task")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.query_one("#details").update(f"Selected: {event.button.label}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        new_task = TaskButton(event.value)
        self.query("#left-panel VerticalScroll")[1].mount(new_task)
        self.query_one("#new-task").value = ""


if __name__ == "__main__":
    app = SimpleServerApp()
    app.run()
