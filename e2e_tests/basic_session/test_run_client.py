from llama_deploy import AsyncLlamaDeployClient, ControlPlaneConfig, LlamaDeployClient


def test_run_client():
    client = LlamaDeployClient(ControlPlaneConfig(), timeout=10)

    # sanity check
    sessions = client.list_sessions()
    assert len(sessions) == 0, "Sessions list is not empty"

    # create a session
    session = client.create_session()

    # kick off run
    _ = session.run("session_workflow", arg1="hello_world")

    # kick off another run
    res = session.run("session_workflow", arg1="hello_world")

    # if the session state is working across runs,
    # the count should be 2
    assert res == "2", f"Session state is not working across runs, result was {res}"

    # delete the session
    client.delete_session(session.session_id)

    # sanity check
    sessions = client.list_sessions()
    assert len(sessions) == 0, "Sessions list is not empty"


async def test_run_client_async():
    client = AsyncLlamaDeployClient(ControlPlaneConfig(), timeout=10)

    # sanity check
    sessions = await client.list_sessions()
    assert len(sessions) == 0, "Sessions list is not empty"

    # create a session
    session = await client.create_session()

    # kick off run
    _ = await session.run("session_workflow", arg1="hello_world")

    # kick off another run
    res = await session.run("session_workflow", arg1="hello_world")

    # if the session state is working across runs,
    # the count should be 2
    assert res == "2", f"Session state is not working across runs, result was {res}"

    # delete the session
    await client.delete_session(session.session_id)

    # sanity check
    sessions = await client.list_sessions()
    assert len(sessions) == 0, "Sessions list is not empty"


if __name__ == "__main__":
    import asyncio

    print("Running async test")
    asyncio.run(test_run_client_async())

    print("Running sync test")
    test_run_client()
