import json

import click
import httpx


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
@click.pass_context
def run(
    ctx: click.Context,
    global_config: tuple,
    deployment: str,
    arg: tuple[tuple[str, str]],
    service: str,
) -> None:
    server_url, disable_ssl, timeout = global_config
    deploy_url = f"{server_url}/deployments/{deployment}/tasks/run"
    payload = {"input": json.dumps(dict(arg))}
    if service:
        payload["agent_id"] = service

    resp = httpx.post(deploy_url, verify=not disable_ssl, json=payload, timeout=timeout)

    if resp.status_code >= 400:
        raise click.ClickException(resp.json().get("detail"))
    else:
        click.echo(resp.json())
