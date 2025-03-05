import click

from llama_deploy import Client
from llama_deploy.types.apiserver import StatusEnum

from .internal.config import ConfigProfile


@click.command()
@click.pass_obj  # config_profile
def status(config_profile: ConfigProfile) -> None:
    """Print the API Server status."""
    client = Client(
        api_server_url=config_profile.server,
        disable_ssl=config_profile.insecure,
        timeout=config_profile.timeout,
    )

    try:
        status = client.sync.apiserver.status()
    except Exception as e:
        raise click.ClickException(str(e))

    if status.status == StatusEnum.HEALTHY:
        click.echo("LlamaDeploy is up and running.")
        if status.deployments:
            click.echo("\nActive deployments:")
            for d in status.deployments:
                click.echo(f"- {d}")
        else:
            click.echo("\nCurrently there are no active deployments")
    else:
        click.echo(f"LlamaDeploy is unhealthy: {status.status_message}")
