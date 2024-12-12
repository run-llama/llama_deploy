import pytest

from llama_deploy import Client


@pytest.mark.e2e
def test_run_client(services):
    client = Client(timeout=10)

    # sanity check
    sessions = client.sync.core.sessions.list()
    assert len(sessions) == 0, "Sessions list is not empty"

    # test streaming
    session = client.sync.core.sessions.create()

    # kick off run
    task_id = session.run_nowait("streaming_workflow", arg1="hello_world")

    num_events = 0
    for event in session.get_task_result_stream(task_id):
        if "progress" in event:
            num_events += 1
            if num_events == 1:
                assert event["progress"] == 0.3
            elif num_events == 2:
                assert event["progress"] == 0.6
            elif num_events == 3:
                assert event["progress"] == 0.9

    # get final result
    final_result = session.get_task_result(task_id)
    assert final_result.result == "hello_world_result_result_result"  # type: ignore

    # delete everything
    client.sync.core.sessions.delete(session.id)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_run_client_async(services):
    client = Client(timeout=10)

    # test streaming
    session = await client.core.sessions.create()

    # kick off run
    task_id = await session.run_nowait("streaming_workflow", arg1="hello_world")

    num_events = 0
    async for event in session.get_task_result_stream(task_id):
        if "progress" in event:
            num_events += 1
            if num_events == 1:
                assert event["progress"] == 0.3
            elif num_events == 2:
                assert event["progress"] == 0.6
            elif num_events == 3:
                assert event["progress"] == 0.9

    final_result = await session.get_task_result(task_id)
    assert final_result.result == "hello_world_result_result_result"  # type: ignore

    # delete everything
    await client.core.sessions.delete(session.id)
