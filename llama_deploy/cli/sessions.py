import click

from llama_deploy import Client

from .internal.config import ConfigProfile


@click.group
def sessions() -> None:
    """Manage sessions for a given deployment."""
    pass


@click.command()
@click.pass_obj  # config_profile
@click.option(
    "-d", "--deployment", required=True, is_flag=False, help="Deployment name"
)
@click.pass_context
def create(
    ctx: click.Context,
    config_profile: ConfigProfile,
    deployment: str,
) -> None:
    client = Client(
        api_server_url=config_profile.server,
        disable_ssl=config_profile.insecure,
        timeout=config_profile.timeout,
    )

    try:
        d = client.sync.apiserver.deployments.get(deployment)
        session_def = d.sessions.create()
    except Exception as e:
        raise click.ClickException(str(e))

    click.echo(session_def)


sessions.add_command(create)
