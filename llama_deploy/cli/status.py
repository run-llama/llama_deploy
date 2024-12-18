import click

from llama_deploy import Client
from llama_deploy.types.apiserver import StatusEnum


@click.command()
@click.pass_obj  # global_config
def status(global_config: tuple) -> None:
    server_url, disable_ssl, timeout = global_config
    client = Client(api_server_url=server_url, disable_ssl=disable_ssl, timeout=timeout)

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
