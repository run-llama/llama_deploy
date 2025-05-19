import threading
from pathlib import Path

import click
import uvicorn
from prometheus_client import start_http_server
from tenacity import Retrying, stop_after_attempt, wait_fixed

from llama_deploy import Client
from llama_deploy.apiserver import settings


@click.command()
@click.option("--local", is_flag=True)
@click.argument(
    "deployment_file",
    required=False,
    type=click.Path(dir_okay=False, resolve_path=True, path_type=Path),  # type: ignore
)
def serve(local: bool, deployment_file: Path | None) -> None:
    """Run the API Server in the foreground."""
    if settings.prometheus_enabled:
        start_http_server(settings.prometheus_port)

    if deployment_file:
        settings.deployments_path = deployment_file.parent

    server = uvicorn.Server(
        uvicorn.Config(
            "llama_deploy.apiserver:app",
            host="localhost",
            port=4501,
        )
    )
    t = threading.Thread(target=server.run)
    t.daemon = True
    t.start()

    if deployment_file:
        client = Client()
        retrying = Retrying(stop=stop_after_attempt(5), wait=wait_fixed(1))
        for attempt in retrying:
            with attempt:
                client.sync.apiserver.deployments.create(
                    deployment_file.open("rb"), skip_sync=local
                )

        try:
            t.join()
        except KeyboardInterrupt:
            print("Shutting down...")
