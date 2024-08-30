import httpx
import logging
import pprint
from typing import Any, Optional

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Button, Header, Footer, Static, Input

from llama_deploy.app.components.human_list import HumanTaskList
from llama_deploy.app.components.service_list import ServicesList
from llama_deploy.app.components.task_list import TasksList
from llama_deploy.app.components.types import ButtonType
from llama_deploy.types import TaskDefinition


class LlamaAgentsMonitor(App):
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

    #right-panel VerticalScroll {
        max-height: 100%;
    }

    Button {
        width: 100%;
        margin-bottom: 1;
    }

    #details {
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
    selected_service_type = reactive("")
    selected_service_url = reactive("")

    def __init__(self, control_plane_url: str, **kwargs: Any):
        self.control_plane_url = control_plane_url
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield Header()
        with Static(id="left-panel"):
            yield ServicesList(id="services", control_plane_url=self.control_plane_url)
            yield TasksList(id="tasks", control_plane_url=self.control_plane_url)
        with VerticalScroll(id="right-panel"):
            yield Static("Task or service details", id="details")
        yield Input(placeholder="Enter: New task", id="new-task")
        yield Footer()

    async def on_mount(self) -> None:
        self.set_interval(5, self.refresh_details)

    async def watch_details(self, new_details: str) -> None:
        if not new_details:
            return

        selected_type = ButtonType(new_details.split(":")[0].strip())

        if selected_type == ButtonType.SERVICE:
            self.query_one("#details").update(new_details)
        elif selected_type == ButtonType.TASK:
            self.query_one("#details").update(new_details)

    async def watch_selected_service_type(self, new_service_type: str) -> None:
        if not new_service_type:
            return

        if new_service_type == "human_service":
            await self.query_one("#right-panel").mount(
                HumanTaskList(self.selected_service_url), after=0
            )
        else:
            try:
                await self.query_one(HumanTaskList).remove()
            except Exception:
                # not mounted yet
                pass

    async def refresh_details(
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
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.get(
                    f"{self.control_plane_url}/services/{selected_label}"
                )
                service_def = response.json()

                service_dict = service_def
                service_url = ""
                if service_def.get("host") and service_def.get("port"):
                    service_url = f"http://{service_def['host']}:{service_def['port']}"
                    response = await client.get(f"{service_url}/")
                    service_dict = response.json()

            # format the service details nicely
            service_string = pprint.pformat(service_dict)

            self.details = (
                f"{selected_type.value}: {selected_label}\n\n{service_string}"
            )

            self.selected_service_url = service_url
            self.selected_service_type = service_dict.get("type")
        elif selected_type == ButtonType.TASK:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.get(
                    f"{self.control_plane_url}/tasks/{selected_label}"
                )
                task_dict = response.json()

            # flatten the TaskResult object
            if task_dict["state"].get("result"):
                task_dict["state"]["result"] = task_dict["state"]["result"]["result"]

            # format the task details nicely
            task_string = pprint.pformat(task_dict)

            self.details = f"{selected_type.value}: {selected_label}\n\n{task_string}"
            self.selected_service_type = ""
            self.selected_service_url = ""

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        # Update the details panel with the selected item
        await self.refresh_details(
            button_type=event.button.type, selected_label=event.button.label
        )

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        new_task = TaskDefinition(input=event.value).model_dump()
        async with httpx.AsyncClient(timeout=120.0) as client:
            await client.post(f"{self.control_plane_url}/tasks", json=new_task)

        # clear the input
        self.query_one("#new-task").value = ""


def run(control_plane_url: str = "http://127.0.0.1:8000") -> None:
    # remove info logging for httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)

    app = LlamaAgentsMonitor(control_plane_url=control_plane_url)
    app.run()


if __name__ == "__main__":
    run()
