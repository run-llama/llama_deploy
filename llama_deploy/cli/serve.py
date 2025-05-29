import os
import subprocess
from pathlib import Path

import click
from prometheus_client import start_http_server
from tenacity import RetryError, Retrying, stop_after_attempt, wait_fixed

from llama_deploy import Client
from llama_deploy.apiserver import settings

RETRY_WAIT_SECONDS = 1


@click.command()
@click.argument(
    "deployment_file",
    required=False,
    type=click.Path(dir_okay=False, resolve_path=True, path_type=Path),  # type: ignore
)
def serve(deployment_file: Path | None) -> None:
    """Run the API Server in the foreground."""
    if settings.prometheus_enabled:
        start_http_server(settings.prometheus_port)

    env = os.environ.copy()
    if deployment_file:
        env["LLAMA_DEPLOY_APISERVER_DEPLOYMENTS_PATH"] = str(deployment_file.parent)

    uvicorn_p = subprocess.Popen(
        [
            "uvicorn",
            "llama_deploy.apiserver:app",
            "--host",
            "localhost",
            "--port",
            "4501",
        ],
        env=env,
    )

    if deployment_file:
        client = Client()
        retrying = Retrying(
            stop=stop_after_attempt(5), wait=wait_fixed(RETRY_WAIT_SECONDS)
        )
        try:
            for attempt in retrying:
                with attempt:
                    client.sync.apiserver.deployments.create(
                        deployment_file.open("rb"),
                        base_path=deployment_file.parent,
                        local=True,
                    )
        except RetryError:
            uvicorn_p.terminate()
            raise click.ClickException("Failed to create deployment")

    try:
        uvicorn_p.wait()
    except KeyboardInterrupt:
        print("Shutting down...")
