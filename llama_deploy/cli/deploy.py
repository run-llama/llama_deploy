from typing import IO

import click

from llama_deploy import Client

from .internal.config import ConfigProfile


@click.command()
@click.pass_obj  # config_profile
@click.option("--reload", is_flag=True)
@click.argument("deployment_config_file", type=click.File("rb"))
def deploy(
    config_profile: ConfigProfile, reload: bool, deployment_config_file: IO
) -> None:
    """Create or reload a deployment."""
    client = Client(
        api_server_url=config_profile.server,
        disable_ssl=config_profile.insecure,
        timeout=config_profile.timeout,
    )

    try:
        deployment = client.sync.apiserver.deployments.create(
            deployment_config_file, reload
        )
    except Exception as e:
        raise click.ClickException(str(e))

    click.echo(f"Deployment successful: {deployment.id}")
