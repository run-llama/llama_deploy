import pytest

from llama_deploy import Client


def test_run_client(services):
    client = Client(timeout=20)

    # sanity check
    sessions = client.sync.core.sessions.list()
    assert len(sessions) == 0, "Sessions list is not empty"

    # test streaming
    session = client.sync.core.sessions.create()

    # kick off run
    task_id = session.run_nowait("streaming_workflow", arg1="hello_world")

    progress_received = []
    for event in session.get_task_result_stream(task_id):
        if "progress" in event:
            progress_received.append(event["progress"])
    assert progress_received == [0.3, 0.6, 0.9]

    # get final result
    final_result = session.get_task_result(task_id)
    assert final_result.result == "hello_world_result_result_result"  # type: ignore

    # delete everything
    client.sync.core.sessions.delete(session.id)


@pytest.mark.asyncio
async def test_run_client_async(services):
    client = Client(timeout=20)

    # test streaming
    session = await client.core.sessions.create()

    # kick off run
    task_id = await session.run_nowait("streaming_workflow", arg1="hello_world")

    progress_received = []
    async for event in session.get_task_result_stream(task_id):
        if "progress" in event:
            progress_received.append(event["progress"])
    assert progress_received == [0.3, 0.6, 0.9]

    final_result = await session.get_task_result(task_id)
    assert final_result.result == "hello_world_result_result_result"  # type: ignore

    # delete everything
    await client.core.sessions.delete(session.id)
