import os
import subprocess
import time

import requests


def test_apiserver_entrypoint():
    # Customize host and port
    env = os.environ.copy()
    env["LLAMA_DEPLOY_APISERVER_HOST"] = "localhost"
    env["LLAMA_DEPLOY_APISERVER_PORT"] = "4502"
    # Start the API server as a subprocess
    process = subprocess.Popen(
        ["python", "-m", "llama_deploy.apiserver"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    try:
        # Wait a bit for the server to start
        time.sleep(2)

        response = requests.get("http://localhost:4502/status")
        assert response.status_code == 200
    finally:
        # Clean up: terminate the server process
        process.terminate()
        process.wait()
