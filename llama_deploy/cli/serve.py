import subprocess
import sys

import click


@click.command()
def serve() -> None:
    """Run the API Server in the foreground."""
    try:
        subprocess.run([sys.executable, "-m", "llama_deploy.apiserver"], check=True)
    except subprocess.CalledProcessError as e:
        click.echo(f"Error starting API server: {e}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("API server stopped.")
