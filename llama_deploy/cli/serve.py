import click
import uvicorn
from prometheus_client import start_http_server

from llama_deploy.apiserver import settings


@click.command()
@click.option("--skip-sync", is_flag=True)
def serve(skip_sync: bool) -> None:
    """Run the API Server in the foreground."""
    if settings.prometheus_enabled:
        start_http_server(settings.prometheus_port)

    uvicorn.run(
        "llama_deploy.apiserver:app",
        host=settings.host,
        port=settings.port,
    )
