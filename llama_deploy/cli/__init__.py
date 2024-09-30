import click

from .deploy import deploy
from .run import run
from .status import status


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
@click.version_option(prog_name="llamactl")
@click.option("-s", "--server", default="http://localhost:4501", help="Apiserver URL")
@click.option(
    "-k",
    "--insecure",
    default=False,
    is_flag=True,
    help="Disable SSL certificate verification",
)
@click.option(
    "-t",
    "--timeout",
    default=None,
    type=float,
    help="Timeout on apiserver HTTP requests",
)
@click.pass_context
def llamactl(
    ctx: click.Context, server: str, insecure: bool, timeout: float | None
) -> None:
    ctx.obj = server, insecure, timeout
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())  # show the help if no subcommand was provided


llamactl.add_command(deploy)
llamactl.add_command(run)
llamactl.add_command(status)
