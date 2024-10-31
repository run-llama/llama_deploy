import asyncio
import pytest
import time

from llama_deploy import AsyncLlamaDeployClient, ControlPlaneConfig, LlamaDeployClient
from llama_index.core.workflow.events import HumanResponseEvent


@pytest.mark.e2ehitl
def test_run_client(services):
    client = LlamaDeployClient(ControlPlaneConfig(), timeout=10)

    # sanity check
    sessions = client.list_sessions()
    assert len(sessions) == 0, "Sessions list is not empty"

    # create a session
    session = client.create_session()

    # kick off run
    task_id = session.run_nowait("hitl_workflow")

    # send event
    session.send_event(
        ev=HumanResponseEvent(response="42"),
        service_name="hitl_workflow",
        task_id=task_id,
    )

    # get final result, polling to wait for workflow to finish after send event
    final_result = None
    while final_result is None:
        final_result = session.get_task_result(task_id)
        time.sleep(0.1)
    assert final_result.result == "42", "The human's response is not consistent."

    # delete the session
    client.delete_session(session.session_id)
    sessions = client.list_sessions()
    assert len(sessions) == 0, "Sessions list is not empty"


@pytest.mark.e2ehitl
@pytest.mark.asyncio
async def test_run_client_async(services):
    client = AsyncLlamaDeployClient(ControlPlaneConfig(), timeout=10)

    # sanity check
    sessions = await client.list_sessions()
    assert len(sessions) == 0, "Sessions list is not empty"

    # create a session
    session = await client.create_session()

    # kick off run
    task_id = await session.run_nowait("hitl_workflow")

    # send event
    await session.send_event(
        ev=HumanResponseEvent(response="42"),
        service_name="hitl_workflow",
        task_id=task_id,
    )

    # get final result, polling to wait for workflow to finish after send event
    final_result = None
    while final_result is None:
        final_result = await session.get_task_result(task_id)
        asyncio.sleep(0.1)
    assert final_result.result == "42", "The human's response is not consistent."

    # delete the session
    await client.delete_session(session.session_id)
    sessions = await client.list_sessions()
    assert len(sessions) == 0, "Sessions list is not empty"
