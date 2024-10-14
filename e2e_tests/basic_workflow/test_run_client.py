import pytest

from llama_deploy import AsyncLlamaDeployClient, ControlPlaneConfig, LlamaDeployClient


@pytest.mark.e2e
def test_run_client(workflow):
    client = LlamaDeployClient(ControlPlaneConfig(), timeout=10)

    # test connections
    assert (
        len(client.list_services()) == 1
    ), f"Expected 1 service, got {client.list_services()}"
    assert (
        len(client.list_sessions()) == 0
    ), f"Expected 0 sessions, got {client.list_sessions()}"

    # test create session
    session = client.get_or_create_session("fake_session_id")
    sessions = client.list_sessions()
    assert len(sessions) == 1, f"Expected 1 session, got {sessions}"
    assert (
        sessions[0].session_id == session.session_id
    ), f"Expected session id to be {session.session_id}, got {sessions[0].session_id}"

    # test run with session
    result = session.run("outer", arg1="hello_world")
    assert result == "hello_world_result"

    # test number of tasks
    tasks = session.get_tasks()
    assert len(tasks) == 1, f"Expected 1 task, got {len(tasks)} tasks"
    assert (
        tasks[0].agent_id == "outer"
    ), f"Expected id to be 'outer', got {tasks[0].agent_id}"

    # delete everything
    client.delete_session(session.session_id)
    assert (
        len(client.list_sessions()) == 0
    ), f"Expected 0 sessions, got {client.list_sessions()}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_run_client_async(workflow):
    client = AsyncLlamaDeployClient(ControlPlaneConfig(), timeout=10)

    # test connections
    assert (
        len(await client.list_services()) == 1
    ), f"Expected 1 service, got {await client.list_services()}"
    assert (
        len(await client.list_sessions()) == 0
    ), f"Expected 0 sessions, got {await client.list_sessions()}"

    # test create session
    session = await client.get_or_create_session("fake_session_id")
    sessions = await client.list_sessions()
    assert len(sessions) == 1, f"Expected 1 session, got {sessions}"
    assert (
        sessions[0].session_id == session.session_id
    ), f"Expected session id to be {session.session_id}, got {sessions[0].session_id}"

    # test run with session
    result = await session.run("outer", arg1="hello_world")
    assert result == "hello_world_result"

    # test number of tasks
    tasks = await session.get_tasks()
    assert len(tasks) == 1, f"Expected 1 task, got {len(tasks)} tasks"
    assert (
        tasks[0].agent_id == "outer"
    ), f"Expected id to be 'outer', got {tasks[0].agent_id}"

    # delete everything
    await client.delete_session(session.session_id)
    assert (
        len(await client.list_sessions()) == 0
    ), f"Expected 0 sessions, got {await client.list_sessions()}"
