from pathlib import Path

import click

from llama_deploy import Client

from .internal.config import ConfigProfile


@click.command()
@click.pass_obj  # config_profile
@click.option("--reload", is_flag=True)
@click.option(
    "--base-path",
    required=False,
    type=click.Path(file_okay=False, resolve_path=True, path_type=Path),  # type: ignore
)
@click.argument(
    "deployment_config_file",
    type=click.Path(dir_okay=False, resolve_path=True, path_type=Path),  # type: ignore
)
def deploy(
    config_profile: ConfigProfile,
    reload: bool,
    deployment_config_file: Path,
    base_path: Path | None,
) -> None:
    """Create or reload a deployment."""
    client = Client(
        api_server_url=config_profile.server,
        disable_ssl=config_profile.insecure,
        timeout=config_profile.timeout,
    )

    final_base_path = base_path or deployment_config_file.parent

    try:
        with open(deployment_config_file, "rb") as f:
            deployment = client.sync.apiserver.deployments.create(
                f,
                base_path=final_base_path,
                reload=reload,
            )
    except Exception as e:
        raise click.ClickException(str(e))

    click.echo(f"Deployment successful: {deployment.id}")
