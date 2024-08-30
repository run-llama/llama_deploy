import httpx
from typing import Any, List

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import Button, Static

from llama_deploy.app.components.types import ButtonType


class TaskButton(Button):
    type: ButtonType = ButtonType.TASK


class TasksList(Static):
    tasks: List[str] = reactive([])

    def __init__(self, control_plane_url: str, **kwargs: Any):
        self.control_plane_url = control_plane_url
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="tasks-scroll"):
            for task in self.tasks:
                yield TaskButton(task)

    async def on_mount(self) -> None:
        self.set_interval(5, self.refresh_tasks)

    async def refresh_tasks(self) -> None:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(f"{self.control_plane_url}/tasks")
            tasks_dict = response.json()

        new_tasks = []
        for task_id in tasks_dict:
            new_tasks.append(task_id)

        self.tasks = [*new_tasks]

    async def watch_tasks(self, new_tasks: List[str]) -> None:
        try:
            tasks_scroll = self.query_one("#tasks-scroll")
            await tasks_scroll.remove_children()
            for task in new_tasks:
                await tasks_scroll.mount(TaskButton(task))
        except Exception:
            pass
