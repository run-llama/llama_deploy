import httpx
from typing import Any, List

from textual.app import ComposeResult
from textual.containers import VerticalScroll, Container
from textual.reactive import reactive
from textual.widgets import Button, Static, Input

from llama_deploy.app.components.types import ButtonType
from llama_deploy.types import HumanResponse, TaskDefinition


class HumanTaskButton(Button):
    type: ButtonType = ButtonType.HUMAN
    task_id: str = ""


class HumanTaskList(Static):
    tasks: List[TaskDefinition] = reactive([])
    selected_task: str = reactive("")
    selected_task_id: str = reactive("")

    def __init__(self, human_service_url: str, **kwargs: Any):
        self.human_service_url = human_service_url
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="human-tasks-scroll"):
            for task in self.tasks:
                button = HumanTaskButton(task.input)
                button.task_id = task.task_id
                yield button

    async def on_mount(self) -> None:
        self.set_interval(2, self.refresh_tasks)

    async def refresh_tasks(self) -> None:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(f"{self.human_service_url}/tasks")
            tasks = response.json()

        new_tasks = []
        for task in tasks:
            new_tasks.append(TaskDefinition(**task))

        self.tasks = [*new_tasks]

    async def watch_tasks(self, new_tasks: List[TaskDefinition]) -> None:
        try:
            tasks_scroll = self.query_one("#human-tasks-scroll")
            await tasks_scroll.remove_children()
            for task in new_tasks:
                button = HumanTaskButton(task.input)
                button.task_id = task.task_id
                await tasks_scroll.mount(button)
        except Exception:
            pass

    async def watch_selected_task(self, new_task: str) -> None:
        if not new_task:
            return

        try:
            await self.query_one("#respond").remove()
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
        await self.mount(container)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # Update the details panel with the selected item
        self.selected_task = event.button.label
        self.selected_task_id = event.button.task_id

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        response = HumanResponse(result=event.value).model_dump()
        async with httpx.AsyncClient(timeout=120.0) as client:
            await client.post(
                f"{self.human_service_url}/tasks/{self.selected_task_id}/handle",
                json=response,
            )

        # remove the input container
        await self.query_one("#respond").remove()

        # remove the task from the list
        new_tasks = [
            task for task in self.tasks if task.task_id != self.selected_task_id
        ]
        self.tasks = [*new_tasks]
