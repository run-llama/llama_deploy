import click
import httpx


@click.command()
@click.pass_obj  # global_config
@click.option("-n", "--name")
@click.argument("deployment_config_file", type=click.File("r"))
def deploy(global_config: tuple, deployment_config_file: str) -> None:
    server_url, disable_ssl = global_config
    deploy_url = f"{server_url}/deployments/create/"

    with open(deployment_config_file, "rb") as file:
        files = {"file": (deployment_config_file, file)}
        resp = httpx.post(deploy_url, files=files, verify=not disable_ssl)

    if resp.status_code >= 400:
        click.echo(f"Error: {resp.json().get('detail')}")
    else:
        click.echo(f"Deployment successful: {resp.json().get('name')}")
