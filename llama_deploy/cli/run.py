import json

import click

from llama_deploy import Client
from llama_deploy.types import TaskDefinition


@click.command()
@click.pass_obj  # global_config
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
    global_config: tuple,
    deployment: str,
    arg: tuple[tuple[str, str]],
    service: str,
    session_id: str,
) -> None:
    server_url, disable_ssl, timeout = global_config
    client = Client(api_server_url=server_url, disable_ssl=disable_ssl, timeout=timeout)

    payload = {"input": json.dumps(dict(arg))}
    if service:
        payload["agent_id"] = service
    if session_id:
        payload["session_id"] = session_id

    try:
        d = client.sync.apiserver.deployments.get(deployment)
        result = d.tasks.run(TaskDefinition(**payload))
    except Exception as e:
        raise click.ClickException(str(e))

    click.echo(result)
