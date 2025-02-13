import pytest

from llama_deploy import Client


def test_run_client(workflow):
    client = Client(timeout=10)

    # test connections
    assert len(client.sync.core.services.list()) == 1
    assert len(client.sync.core.sessions.list()) == 0

    # test create session
    session = client.sync.core.sessions.get_or_create("fake_session_id")
    sessions = client.sync.core.sessions.list()
    assert len(sessions) == 1
    assert sessions[0].id == session.id

    # test run with session
    result = session.run("outer", arg1="hello_world")
    assert result == "hello_world_result"

    # test number of tasks
    tasks = session.get_tasks()
    assert len(tasks) == 1
    assert tasks[0].service_id == "outer"

    # delete everything
    client.sync.core.sessions.delete(session.id)
    assert len(client.sync.core.sessions.list()) == 0


@pytest.mark.asyncio
async def test_run_client_async(workflow):
    client = Client(timeout=10)

    # test connections
    assert len(await client.core.services.list()) == 1
    assert len(await client.core.sessions.list()) == 0

    # test create session
    session = await client.core.sessions.get_or_create("fake_session_id")
    sessions = await client.core.sessions.list()
    assert len(sessions) == 1, f"Expected 1 session, got {sessions}"
    assert sessions[0].id == session.id

    # test run with session
    result = await session.run("outer", arg1="hello_world")
    assert result == "hello_world_result"

    # test number of tasks
    tasks = await session.get_tasks()
    assert len(tasks) == 1, f"Expected 1 task, got {len(tasks)} tasks"
    assert (
        tasks[0].service_id == "outer"
    ), f"Expected id to be 'outer', got {tasks[0].service_id}"

    # delete everything
    await client.core.sessions.delete(session.id)
    assert len(await client.core.sessions.list()) == 0
