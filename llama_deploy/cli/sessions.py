import click

from llama_deploy import Client


@click.group
def sessions() -> None:
    pass


@click.command()
@click.pass_obj  # global_config
@click.option(
    "-d", "--deployment", required=True, is_flag=False, help="Deployment name"
)
@click.pass_context
def create(
    ctx: click.Context,
    global_config: tuple,
    deployment: str,
) -> None:
    server_url, disable_ssl, timeout = global_config
    client = Client(api_server_url=server_url, disable_ssl=disable_ssl, timeout=timeout)

    try:
        d = client.sync.apiserver.deployments.get(deployment)
        session_def = d.sessions.create()
    except Exception as e:
        raise click.ClickException(str(e))

    click.echo(session_def)


sessions.add_command(create)
