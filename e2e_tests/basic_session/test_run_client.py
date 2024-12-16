import pytest

from llama_deploy import Client


def test_run_client(workflow):
    client = Client(timeout=10)

    # create session
    session = client.sync.core.sessions.create()

    # test run with session
    result = session.run("session_workflow")
    assert result == "1"

    # run again
    result = session.run("session_workflow")
    assert result == "2"

    # create new session and run
    session = client.sync.core.sessions.create()
    result = session.run("session_workflow")
    assert result == "1"


@pytest.mark.asyncio
async def test_run_client_async(workflow):
    client = Client(timeout=10)

    # create session
    session = await client.core.sessions.create()

    # run
    result = await session.run("session_workflow")
    assert result == "1"

    # run again
    result = await session.run("session_workflow")
    assert result == "2"

    # create new session and run
    session = await client.core.sessions.create()
    result = await session.run("session_workflow")
    assert result == "1"
