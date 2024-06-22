import httpx
import pprint
from enum import Enum
from typing import Any, List, Optional

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Button, Header, Footer, Static, Input

from agentfile.types import TaskDefinition


class ButtonType(str, Enum):
    SERVICE = "Service"
    TASK = "Task"


class ServiceButton(Button):
    type: ButtonType = ButtonType.SERVICE


class TaskButton(Button):
    type: ButtonType = ButtonType.TASK


class ServicesList(Static):
    services = reactive([])

    def __init__(self, control_plane_url: str, **kwargs: Any):
        self.control_plane_url = control_plane_url
        super().__init__(**kwargs)

        self.refresh_services()

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="services-scroll"):
            for service in self.services:
                yield ServiceButton(service)

    def on_mount(self) -> None:
        self.set_interval(5, self.refresh_services)

    def refresh_services(self) -> None:
        with httpx.Client() as client:
            response = client.get(f"{self.control_plane_url}/services")
            services_dict = response.json()

        new_services = []
        for service_name in services_dict:
            new_services.append(service_name)

        self.services = [*new_services]

    def watch_services(self, new_services: List[str]) -> None:
        try:
            services_scroll = self.query_one("#services-scroll")
            services_scroll.remove_children()
            for service in new_services:
                services_scroll.mount(ServiceButton(service))
        except Exception:
            pass


class TasksList(Static):
    tasks = reactive([])

    def __init__(self, control_plane_url: str, **kwargs: Any):
        self.control_plane_url = control_plane_url
        super().__init__(**kwargs)

        self.refresh_tasks()

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="tasks-scroll"):
            for task in self.tasks:
                yield TaskButton(task)

    def on_mount(self) -> None:
        self.set_interval(5, self.refresh_tasks)

    def refresh_tasks(self) -> None:
        with httpx.Client() as client:
            response = client.get(f"{self.control_plane_url}/tasks")
            tasks_dict = response.json()

        new_tasks = []
        for task_id in tasks_dict:
            new_tasks.append(task_id)

        self.tasks = [*new_tasks]

    def watch_tasks(self, new_tasks: List[str]) -> None:
        try:
            tasks_scroll = self.query_one("#tasks-scroll")
            tasks_scroll.remove_children()
            for task in new_tasks:
                tasks_scroll.mount(TaskButton(task))
        except Exception:
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

    #tasks {
        height: auto;
        max-height: 50%;
    }

    #services {
        height: auto;
        max-height: 50%;
    }

    VerticalScroll {
        height: auto;
        max-height: 100%;
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
        text-align: left;
    }

    #new-task {
        dock: bottom;
        margin-bottom: 1;
        width: 100%;
    }
    """

    details = reactive("")

    def __init__(self, control_plane_url: str, **kwargs: Any):
        self.control_plane_url = control_plane_url
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield Header()
        with Static(id="left-panel"):
            yield ServicesList(id="services", control_plane_url=self.control_plane_url)
            yield TasksList(id="tasks", control_plane_url=self.control_plane_url)
        with Static(id="right-panel"):
            yield Static("Task or service details", id="details")
        yield Input(placeholder="Enter: New task", id="new-task")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(5, self.refresh_details)

    def watch_details(self, new_details: str) -> None:
        if not new_details:
            return

        selected_type = ButtonType(new_details.split(":")[0].strip())

        if selected_type == ButtonType.SERVICE:
            self.query_one("#details").update(new_details)
        elif selected_type == ButtonType.TASK:
            self.query_one("#details").update(new_details)

    def refresh_details(
        self,
        button_type: Optional[ButtonType] = None,
        selected_label: Optional[str] = None,
    ) -> None:
        if not self.details and button_type is None and selected_label is None:
            return

        selected_type = button_type or ButtonType(self.details.split(":")[0].strip())
        selected_label = (
            selected_label or self.details.split(":")[1].split("\n")[0].strip()
        )

        if selected_type == ButtonType.SERVICE:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.control_plane_url}/services/{selected_label}"
                )
                service_def = response.json()

                service_dict = service_def
                if service_def.get("host") and service_def.get("port"):
                    service_url = f"http://{service_def['host']}:{service_def['port']}"
                    response = client.get(f"{service_url}/")
                    service_dict = response.json()

            # format the service details nicely
            service_string = pprint.pformat(service_dict)

            self.details = (
                f"{selected_type.value}: {selected_label}\n\n{service_string}"
            )
        elif selected_type == ButtonType.TASK:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.control_plane_url}/tasks/{selected_label}"
                )
                task_dict = response.json()

            # format the task details nicely
            task_string = pprint.pformat(task_dict)

            self.details = f"{selected_type.value}: {selected_label}\n\n{task_string}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # Update the details panel with the selected item
        self.refresh_details(
            button_type=event.button.type, selected_label=event.button.label
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        new_task = TaskDefinition(input=event.value).model_dump()
        with httpx.Client() as client:
            client.post(f"{self.control_plane_url}/tasks", json=new_task)

        # clear the input
        self.query_one("#new-task").value = ""


if __name__ == "__main__":
    import logging

    # remove info logging for httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)

    app = SimpleServerApp("http://127.0.0.1:8000")
    app.run()
