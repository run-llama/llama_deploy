import click
from pydantic import AnyHttpUrl
from rich.console import Console
from rich.table import Table

from .internal.config import Config, load_config


def _strtobool(val: str) -> bool:
    """Convert a string representation of truth to True or False.

    Original code from distutils (MIT license).

    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return True
    elif val in ("n", "no", "f", "false", "off", "0"):
        return False
    else:
        raise ValueError("invalid truth value %r" % (val,))


@click.group
@click.pass_context
def config(ctx: click.Context) -> None:
    """Manage configuration profiles and settings.

    Loads the configuration from the specified config file and provides
    commands for viewing and modifying profiles.
    """
    # Get the config file path from the root command
    ctx.obj = load_config(ctx.parent.params["config"])  # type: ignore


@click.command()
@click.pass_obj
def get_profiles(
    config: Config,
) -> None:
    """List all available configuration profiles."""
    table = Table(box=None)
    table.add_column("Current")
    table.add_column("Profile")
    table.add_column("Server url")

    for name, profile in config.profiles.items():
        current = ""
        if name == config.current_profile:
            current = "*"
        table.add_row(current, name, profile.server)

    console = Console()
    console.print(table)


@click.command()
@click.pass_obj  # config_profile
def current_profile(
    config: Config,
) -> None:
    """Display the name of the currently active profile."""
    click.echo(config.current_profile)


@click.command()
@click.pass_obj  # config_profile
@click.argument("profile")
def use_profile(
    config: Config,
    profile: str,
) -> None:
    """Switch to using a different profile.

    Args:
        profile: Name of the profile to switch to

    Raises:
        ClickException: If the specified profile doesn't exist
    """
    if profile not in config.profiles:
        raise click.ClickException(
            f"Cannot find profile '{profile}' in the config file."
        )

    config.current_profile = profile
    config.write()


@click.command()
@click.pass_obj  # config_profile
@click.argument("param")
@click.argument("value")
def set_profile_vars(config: Config, param: str, value: str) -> None:
    """Set a variable for the current profile.

    Args:
        param: The parameter name to set
        value: The value to set for the parameter

    Raises:
        ClickException: If the parameter name is not valid
    """
    # Get the current profile
    current = config.profiles[config.current_profile]
    param = param.strip().lower()

    # Handle the different valid parameters
    try:
        if param == "server":
            AnyHttpUrl(value)
            current.server = value
        elif param == "insecure":
            current.insecure = _strtobool(value)
        elif param == "timeout":
            current.timeout = float(value)
        else:
            raise click.ClickException(f"Unknown parameter '{param}'.")
    except Exception as e:
        raise click.ClickException(
            f"Error setting {param}={value} for profile '{config.current_profile}': {e}"
        )

    # Save the changes
    config.write()
    click.echo(f"Set {param}={value} for profile '{config.current_profile}'")


@click.command()
@click.pass_obj
@click.argument("profile")
def delete_profile(
    config: Config,
    profile: str,
) -> None:
    """Delete a profile from the configuration.

    Args:
        profile: Name of the profile to delete

    Raises:
        ClickException: If the profile doesn't exist or is currently in use
    """
    if profile not in config.profiles:
        raise click.ClickException(
            f"Cannot find profile '{profile}' in the config file."
        )

    # Don't allow deleting the current profile
    if profile == config.current_profile:
        raise click.ClickException(
            f"Cannot delete profile '{profile}' because it is currently in use. "
            "Switch to another profile with 'llamactl config use-profile' first."
        )

    # Delete the profile
    del config.profiles[profile]
    config.write()

    click.echo(f"Profile '{profile}' has been deleted.")


@click.command()
@click.pass_obj
@click.argument("old_name")
@click.argument("new_name")
def rename_profile(
    config: Config,
    old_name: str,
    new_name: str,
) -> None:
    """Rename a profile in the configuration.

    Args:
        old_name: Current name of the profile
        new_name: New name for the profile

    Raises:
        ClickException: If the old profile doesn't exist or the new name is already taken
    """
    # Check if the old profile exists
    if old_name not in config.profiles:
        raise click.ClickException(
            f"Cannot find profile '{old_name}' in the config file."
        )

    # Check if the new name already exists
    if new_name in config.profiles:
        raise click.ClickException(
            f"Profile '{new_name}' already exists in the config file."
        )

    # Add old profile with new name
    config.profiles[new_name] = config.profiles[old_name]

    # Delete old profile
    del config.profiles[old_name]

    # Update current_profile if we're renaming the active profile
    if config.current_profile == old_name:
        config.current_profile = new_name

    # Save changes
    config.write()

    click.echo(f"Profile '{old_name}' has been renamed to '{new_name}'.")


config.add_command(get_profiles)
config.add_command(current_profile)
config.add_command(use_profile)
config.add_command(set_profile_vars)
config.add_command(delete_profile)
config.add_command(rename_profile)
