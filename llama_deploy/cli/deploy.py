from typing import IO

import click

from llama_deploy import Client


@click.command()
@click.pass_obj  # global_config
@click.argument("deployment_config_file", type=click.File("rb"))
def deploy(global_config: tuple, deployment_config_file: IO) -> None:
    server_url, disable_ssl, timeout = global_config
    client = Client(api_server_url=server_url, disable_ssl=disable_ssl, timeout=timeout)

    try:
        deployment = client.sync.apiserver.deployments.create(deployment_config_file)
    except Exception as e:
        raise click.ClickException(str(e))

    click.echo(f"Deployment successful: {deployment.id}")
