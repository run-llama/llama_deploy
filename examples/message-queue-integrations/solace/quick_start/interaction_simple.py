import time
from llama_deploy import LlamaDeployClient, ControlPlaneConfig

# number of times to run the workflow
ITERATION_COUNT = 3
# time to sleep between each run
SLEEP_TIME = 5

# points to deployed control plane
client = LlamaDeployClient(ControlPlaneConfig())

# create a session
session = client.create_session()

# run a workflow
for _ in range(ITERATION_COUNT):
    task_id = session.run_nowait("ping_workflow", arg1="still_alive")

    print("task_id:", task_id)
    for event in session.get_task_result_stream(task_id):
        print("task result:", event)

    time.sleep(SLEEP_TIME)

print("Done")
