import json

import click

from .utils import do_httpx


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
@click.pass_context
def run(
    ctx: click.Context,
    global_config: tuple,
    deployment: str,
    arg: tuple[tuple[str, str]],
) -> None:
    server_url, insecure = global_config
    deploy_url = f"{server_url}/deployments/{deployment}/tasks/create"
    payload = {"input": json.dumps(dict(arg)), "agent_id": "my_workflow"}

    resp = do_httpx("post", deploy_url, verify=not insecure, json=payload)

    if resp.status_code >= 400:
        raise click.ClickException(resp.json().get("detail"))
    else:
        click.echo(resp.json())
