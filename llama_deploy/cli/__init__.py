from pathlib import Path

import click

from .config import config as config_cmd
from .deploy import deploy as deploy_cmd
from .internal.config import DEFAULT_PROFILE_NAME, load_config
from .run import run as run_cmd
from .sessions import sessions as sessions_cmd
from .status import status as status_cmd


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
@click.version_option(prog_name="llamactl")
@click.option(
    "-c",
    "--config",
    type=Path,
    default=None,
    help="Path to llamactl config file",
)
@click.option(
    "-p",
    "--profile",
    type=str,
    default=None,
    help="Configuration profile to use",
)
@click.option(
    "-s",
    "--server",
    type=str,
    default=None,
    help="Apiserver URL",
)
@click.option(
    "-k",
    "--insecure",
    default=None,
    type=bool,
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
    ctx: click.Context,
    config: Path,
    profile: str,
    server: str,
    insecure: bool,
    timeout: float,
) -> None:
    config_obj = load_config(config)
    profile = profile or DEFAULT_PROFILE_NAME
    if profile not in config_obj.profiles:
        raise click.ClickException(f"Profile {profile} does not exist.")
    config_profile = config_obj.profiles[profile]
    # Parameters passed via command line take precedence
    config_profile.server = server or config_profile.server
    config_profile.insecure = insecure or config_profile.insecure
    config_profile.timeout = timeout or config_profile.timeout

    ctx.obj = config_profile
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())  # show the help if no subcommand was provided


llamactl.add_command(deploy_cmd)
llamactl.add_command(run_cmd)
llamactl.add_command(status_cmd)
llamactl.add_command(sessions_cmd)
llamactl.add_command(config_cmd)
