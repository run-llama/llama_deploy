from llama_deploy import AsyncLlamaDeployClient, ControlPlaneConfig, LlamaDeployClient


def test_run_client():
    client = LlamaDeployClient(ControlPlaneConfig(), timeout=10)

    # sanity check
    sessions = client.list_sessions()
    assert len(sessions) == 0, "Sessions list is not empty"

    # test streaming
    session = client.create_session()

    num_events = 0
    for event in session.stream_run("streaming_workflow", arg1="hello_world"):
        if "progress" in event:
            num_events += 1
            if num_events == 1:
                assert event["progress"] == 0.3, "First progress event is not 0.3"
            elif num_events == 2:
                assert event["progress"] == 0.6, "Second progress event is not 0.6"
            elif num_events == 3:
                assert event["progress"] == 0.9, "Third progress event is not 0.9"
        else:
            assert (
                event == "hello_world_result_result_result"
            ), "Final event is not 'hello_world_result_result_result'"

    # delete everything
    client.delete_session(session.session_id)
    sessions = client.list_sessions()
    assert len(sessions) == 0, "Sessions list is not empty"


async def test_run_client_async():
    client = AsyncLlamaDeployClient(ControlPlaneConfig(), timeout=10)

    # sanity check
    sessions = await client.list_sessions()
    assert len(sessions) == 0, "Sessions list is not empty"

    # test streaming
    session = await client.create_session()

    num_events = 0
    async for event in session.stream_run("streaming_workflow", arg1="hello_world"):
        if "progress" in event:
            num_events += 1
            if num_events == 1:
                assert event["progress"] == 0.3, "First progress event is not 0.3"
            elif num_events == 2:
                assert event["progress"] == 0.6, "Second progress event is not 0.6"
            elif num_events == 3:
                assert event["progress"] == 0.9, "Third progress event is not 0.9"
        else:
            assert (
                event == "hello_world_result_result_result"
            ), "Final event is not 'hello_world_result_result_result'"

    # delete everything
    await client.delete_session(session.session_id)
    sessions = await client.list_sessions()
    assert len(sessions) == 0, "Sessions list is not empty"


if __name__ == "__main__":
    import asyncio

    print("Running async test")
    asyncio.run(test_run_client_async())

    print("Running sync test")
    test_run_client()