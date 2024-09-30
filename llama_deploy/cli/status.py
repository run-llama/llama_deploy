import click


from .utils import request


@click.command()
@click.pass_obj  # global_config
def status(global_config: tuple) -> None:
    server_url, disable_ssl, timeout = global_config
    status_url = f"{server_url}/status/"

    r = request("GET", status_url, verify=not disable_ssl, timeout=timeout)
    if r.status_code >= 400:
        body = r.json()
        click.echo(
            f"Llama Deploy is unhealthy: [{r.status_code}] {r.json().get('detail')}"
        )
        return

    click.echo("Llama Deploy is up and running.")
    body = r.json()
    if deployments := body.get("deployments"):
        click.echo("\nActive deployments:")
        for d in deployments:
            click.echo(f"- {d}")
    else:
        click.echo("\nCurrently there are no active deployments")
