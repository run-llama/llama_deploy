import pytest

from llama_deploy import AsyncLlamaDeployClient, ControlPlaneConfig, LlamaDeployClient


@pytest.mark.e2e
def test_run_client(workflow):
    client = LlamaDeployClient(ControlPlaneConfig(), timeout=10)

    # create session
    session = client.get_or_create_session("fake_session_id")

    # test run with session
    result = session.run("session_workflow")
    assert result == "1"

    # run again
    result = session.run("session_workflow")
    assert result == "2"

    # create new session and run
    session = client.get_or_create_session("fake_session_id_2")
    result = session.run("session_workflow")
    assert result == "1"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_run_client_async(workflow):
    client = AsyncLlamaDeployClient(ControlPlaneConfig(), timeout=10)

    # create session
    session = await client.get_or_create_session("fake_session_id")

    # run
    result = await session.run("session_workflow")
    assert result == "1"

    # run again
    result = await session.run("session_workflow")
    assert result == "2"

    # create new session and run
    session = await client.get_or_create_session("fake_session_id_2")
    result = await session.run("session_workflow")
    assert result == "1"
