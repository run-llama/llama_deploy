from typing import Any
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from llama_deploy.control_plane import ControlPlaneConfig, ControlPlaneServer
from llama_deploy.message_queues import SimpleMessageQueueServer
from llama_deploy.messages.base import QueueMessage
from llama_deploy.types import TaskDefinition
from llama_deploy.types.core import ActionTypes


def test_control_plane_init() -> None:
    mq = SimpleMessageQueueServer()
    cp = ControlPlaneServer(mq)  # type: ignore
    assert cp._orchestrator is not None
    assert cp._state_store is not None
    assert cp._config is not None

    assert cp.message_queue == mq
    assert cp.publisher_id.startswith("ControlPlaneServer-")
    assert cp.publish_callback is None

    assert cp.get_topic("msg_type") == "llama_deploy.msg_type"


def test_control_plane_init_state_store() -> None:
    mocked_store = mock.MagicMock()
    with pytest.raises(ValueError):
        ControlPlaneServer(
            SimpleMessageQueueServer(),  # type: ignore
            state_store=mocked_store,
            config=ControlPlaneConfig(state_store_uri="test/uri"),
        )

    cp = ControlPlaneServer(SimpleMessageQueueServer(), state_store=mocked_store)  # type: ignore
    assert cp._state_store == mocked_store

    with mock.patch(
        "llama_deploy.control_plane.server.parse_state_store_uri"
    ) as mocked_parse:
        ControlPlaneServer(
            SimpleMessageQueueServer(),  # type: ignore
            config=ControlPlaneConfig(state_store_uri="test/uri"),
        )
        mocked_parse.assert_called_with("test/uri")


@pytest.mark.asyncio
async def test_process_message() -> None:
    server = ControlPlaneServer(message_queue=mock.AsyncMock())
    server.create_session = mock.AsyncMock()  # type: ignore
    server.add_task_to_session = mock.AsyncMock()  # type: ignore
    server.handle_service_completion = mock.AsyncMock()  # type: ignore
    server.add_stream_to_session = mock.AsyncMock()  # type: ignore

    with pytest.raises(ValueError, match="Invalid field 'data' in QueueMessage: {}"):
        msg = QueueMessage(action=ActionTypes.NEW_TASK)
        await server.process_message(msg)

    msg = QueueMessage(action=ActionTypes.NEW_TASK, data={"input": "foo"})
    await server.process_message(msg)
    server.create_session.assert_awaited_once()
    server.add_task_to_session.assert_awaited_once()

    msg = QueueMessage(
        action=ActionTypes.COMPLETED_TASK,
        data={"task_id": "test-task", "history": [], "result": ""},
    )
    await server.process_message(msg)
    server.handle_service_completion.assert_awaited_once()

    msg = QueueMessage(
        action=ActionTypes.TASK_STREAM,
        data={
            "task_id": "test-task",
            "session_id": "test-session",
            "data": {},
            "index": 0,
        },
    )
    await server.process_message(msg)
    server.add_stream_to_session.assert_awaited_once()

    with pytest.raises(
        ValueError,
        match=r"Action .* not supported by control plane",
    ):
        msg = QueueMessage(action=ActionTypes.REQUEST_FOR_HELP, data={"foo": "bar"})
        await server.process_message(msg)


def test_add_task_to_session_not_found(http_client: TestClient, kvstore: Any) -> None:
    kvstore.aget.return_value = None
    td = TaskDefinition(input="")
    response = http_client.post("/sessions/test_session_id/tasks", json=td.model_dump())
    assert response.status_code == 404


def test_add_task_to_session_populate_session_id(
    http_client: TestClient, kvstore: Any
) -> None:
    kvstore.aget.return_value = {}
    td = TaskDefinition(input="", service_id="test-id")
    response = http_client.post("/sessions/test_session_id/tasks", json=td.model_dump())
    assert response.status_code == 200
    # The second call to aput() contains the updated task definition
    assert kvstore.aput.await_args_list[1].args[1]["session_id"] == "test_session_id"


def test_add_task_to_session_session_id_mismatch(
    http_client: TestClient, kvstore: Any
) -> None:
    kvstore.aget.return_value = {}
    td = TaskDefinition(input="", service_id="test-id", session_id="wrong-id")
    response = http_client.post("/sessions/test-session-id/tasks", json=td.model_dump())
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Wrong task definition: task.session_id is wrong-id but should be test-session-id"
    )
