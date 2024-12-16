import asyncio
import time

import pytest
from llama_index.core.workflow.events import HumanResponseEvent

from llama_deploy import Client


def test_run_client(services):
    client = Client(timeout=10)

    # sanity check
    sessions = client.sync.core.sessions.list()
    assert len(sessions) == 0, "Sessions list is not empty"

    # create a session
    session = client.sync.core.sessions.create()

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
    client.sync.core.sessions.delete(session.id)
    sessions = client.sync.core.sessions.list()
    assert len(sessions) == 0, "Sessions list is not empty"


@pytest.mark.asyncio
async def test_run_client_async(services):
    client = Client(timeout=10)

    # sanity check
    sessions = await client.core.sessions.list()
    assert len(sessions) == 0, "Sessions list is not empty"

    # create a session
    session = await client.core.sessions.create()

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
        await asyncio.sleep(0.1)
    assert final_result.result == "42", "The human's response is not consistent."

    # delete the session
    await client.core.sessions.delete(session.id)
    sessions = await client.core.sessions.list()
    assert len(sessions) == 0, "Sessions list is not empty"
