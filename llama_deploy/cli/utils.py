from typing import Any
from urllib.parse import urlparse

import click
import httpx


def request(
    method: str, url: str | httpx.URL, *args: Any, **kwargs: Any
) -> httpx.Response:
    try:
        return httpx.request(method, url, *args, **kwargs)
    except httpx.ConnectError:
        parsed_url = urlparse(str(url))
        raise click.ClickException(
            "Llama Deploy is not responding, check that the apiserver "
            f"is running at {parsed_url.scheme}://{parsed_url.netloc} and try again."
        )
