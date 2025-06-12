import os
import subprocess
from pathlib import Path
from typing import Optional

import click
from prometheus_client import start_http_server
from tenacity import RetryError, Retrying, stop_after_attempt, wait_fixed

from llama_deploy.apiserver.settings import settings
from llama_deploy.client import Client

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
            "llama_deploy.apiserver.app:app",
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
        except RetryError as e:
            uvicorn_p.terminate()
            last: Optional[BaseException] = e.last_attempt.exception(0)
            last_msg = ""
            if last is not None:
                last_msg = ": " + (
                    last.message if hasattr(last, "message") else str(last)
                )
            raise click.ClickException(f"Failed to create deployment{last_msg}")

    try:
        uvicorn_p.wait()
    except KeyboardInterrupt:
        print("Shutting down...")
