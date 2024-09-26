import click
import httpx


@click.command()
@click.pass_obj  # global_config
def status(global_config: tuple) -> None:
    server_url, disable_ssl = global_config
    status_url = f"{server_url}/status/"

    try:
        r = httpx.get(status_url, verify=not disable_ssl)
    except httpx.ConnectError:
        raise click.ClickException(
            f"Llama Deploy is not responding, check the apiserver address {server_url} is correct and try again."
        )

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
