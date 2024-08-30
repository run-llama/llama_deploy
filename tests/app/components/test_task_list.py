import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from llama_deploy.app.components.task_list import TasksList


@pytest.mark.asyncio
async def test_refresh_tasks() -> None:
    # Mock the response object and its json method
    mock_response = MagicMock()
    mock_response.json.return_value = ["Task1", "Task2"]

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        tasks_list = TasksList("http://example.com")
        await tasks_list.refresh_tasks()

        # Assertions to verify the tasks have been updated
        assert tasks_list.tasks == ["Task1", "Task2"]


@pytest.mark.asyncio
async def test_watch_tasks() -> None:
    tasks_list = TasksList("http://example.com")
    tasks_list.tasks = ["Old Task1", "Old Task2"]

    # Simulate tasks_scroll being part of the component structure
    tasks_scroll = AsyncMock()
    tasks_scroll.remove_children = AsyncMock()
    tasks_scroll.mount = AsyncMock()

    # Patch the query_one method to return our mock scroll object when queried
    with patch.object(tasks_list, "query_one", return_value=tasks_scroll):
        new_tasks = ["New Task1", "New Task2"]
        await tasks_list.watch_tasks(new_tasks)

        # Ensure children are removed and new tasks are mounted
        tasks_scroll.remove_children.assert_called_once()
        assert tasks_scroll.mount.call_count == len(new_tasks)
