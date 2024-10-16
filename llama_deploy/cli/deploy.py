from typing import IO

import click

from llama_deploy.cli.utils import request


@click.command()
@click.pass_obj  # global_config
@click.argument("deployment_config_file", type=click.File("rb"))
def deploy(global_config: tuple, deployment_config_file: IO) -> None:
    server_url, disable_ssl, timeout = global_config
    deploy_url = f"{server_url}/deployments/create"

    files = {"config_file": deployment_config_file.read()}
    resp = request(
        "POST", deploy_url, files=files, verify=not disable_ssl, timeout=timeout
    )

    if resp.status_code >= 400:
        try:
            raise click.ClickException(resp.json().get("detail", resp.text))
        except ValueError:
            raise click.ClickException(resp.text)

    else:
        click.echo(f"Deployment successful: {resp.json().get('name')}")
