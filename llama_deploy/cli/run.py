import json

import click

from llama_deploy import Client
from llama_deploy.types import TaskDefinition

from .internal.config import ConfigProfile


@click.command()
@click.pass_obj  # config_profile
@click.option(
    "-d", "--deployment", required=True, is_flag=False, help="Deployment name"
)
@click.option(
    "-a",
    "--arg",
    multiple=True,
    is_flag=False,
    type=(str, str),
    help="'key value' argument to pass to the task, e.g. '-a age 30'",
)
@click.option("-s", "--service", is_flag=False, help="Service name")
@click.option("-i", "--session-id", is_flag=False, help="Session ID")
@click.pass_context
def run(
    ctx: click.Context,
    config_profile: ConfigProfile,
    deployment: str,
    arg: tuple[tuple[str, str]],
    service: str,
    session_id: str,
) -> None:
    """Run tasks from a given service."""
    client = Client(
        api_server_url=config_profile.server,
        disable_ssl=config_profile.insecure,
        timeout=config_profile.timeout,
    )

    payload = {"input": json.dumps(dict(arg))}
    if service:
        payload["service_id"] = service
    if session_id:
        payload["session_id"] = session_id

    try:
        d = client.sync.apiserver.deployments.get(deployment)
        result = d.tasks.run(TaskDefinition(**payload))
    except Exception as e:
        raise click.ClickException(str(e))

    click.echo(result)
