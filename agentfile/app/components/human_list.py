import httpx
from typing import Any, List

from textual.app import ComposeResult
from textual.containers import VerticalScroll, Container
from textual.reactive import reactive
from textual.widgets import Button, Static, Input

from agentfile.app.components.types import ButtonType
from agentfile.types import HumanResponse, TaskDefinition


class HumanTaskButton(Button):
    type: ButtonType = ButtonType.HUMAN
    task_id: str = ""


class HumanTaskList(Static):
    tasks: List[TaskDefinition] = reactive([])
    selected_task: str = reactive("")

    def __init__(self, human_service_url: str, **kwargs: Any):
        self.human_service_url = human_service_url
        super().__init__(**kwargs)

        self.refresh_tasks()

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="human-tasks-scroll"):
            for task in self.tasks:
                button = HumanTaskButton(task.input)
                button.task_id = task.task_id
                yield button

    def on_mount(self) -> None:
        self.set_interval(5, self.refresh_tasks)

    def refresh_tasks(self) -> None:
        with httpx.Client() as client:
            response = client.get(f"{self.human_service_url}/tasks")
            tasks = response.json()

        new_tasks = []
        for task in tasks:
            new_tasks.append(TaskDefinition(**task))

        self.tasks = [*new_tasks]

    def watch_tasks(self, new_tasks: List[TaskDefinition]) -> None:
        try:
            tasks_scroll = self.query_one("#human-tasks-scroll")
            tasks_scroll.remove_children()
            for task in new_tasks:
                button = HumanTaskButton(task.input)
                button.task_id = task.task_id
                tasks_scroll.mount(button)
        except Exception:
            pass

    def watch_selected_task(self, new_task: str) -> None:
        if not new_task:
            return

        try:
            self.query_one("#respond").remove()
        except Exception:
            # not mounted yet
            pass

        container = Container(
            Static(f"Task: {new_task}"),
            Input(
                placeholder="Type your response here",
            ),
            id="respond",
        )

        # mount the container
        self.mount(container)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # Update the details panel with the selected item
        self.selected_task = event.button.label

    def on_input_submitted(self, event: Input.Submitted) -> None:
        response = HumanResponse(result=event.value).model_dump()
        with httpx.Client() as client:
            client.post(
                f"{self.human_service_url}/tasks/{self.selected_task}/handle",
                json=response,
            )

        # remove the input container
        self.query_one("#respond").remove()

        # remove the task from the list
        new_tasks = [task for task in self.tasks if task.task_id != self.selected_task]
        self.tasks = [*new_tasks]
