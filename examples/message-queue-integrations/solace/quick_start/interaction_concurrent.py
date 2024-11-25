import threading
from llama_deploy import LlamaDeployClient, ControlPlaneConfig

# number of times to run the workflow
ITERATION_COUNT = 3

# Points to deployed control plane
client = LlamaDeployClient(ControlPlaneConfig())


def run_workflow(workflow_name: str):
    """Function to run the workflow in a separate thread."""
    # Create a session
    session = client.create_session()

    # Run a workflow
    task_id = session.run_nowait(workflow_name, arg1="still_alive")

    print(f"task_id for {workflow_name}:", task_id)
    for event in session.get_task_result_stream(task_id):
        print(f"task result for {workflow_name}:", event)

    print(f"Done with {workflow_name}")


# Create and start threads for each workflow
threads = []
for _ in range(ITERATION_COUNT):
    thread = threading.Thread(target=run_workflow, args=("ping_workflow",))
    threads.append(thread)
    thread.start()

# Optionally, wait for all threads to complete
for thread in threads:
    thread.join()
