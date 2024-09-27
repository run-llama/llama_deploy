from typing import cast, Any
from urllib.parse import urlparse

import click
import httpx as httpx


def do_httpx(http_method: str, url: str, *args: Any, **kwargs: Any) -> httpx.Response:
    fn = getattr(httpx, http_method)
    try:
        return cast(httpx.Response, fn(url, *args, **kwargs))
    except httpx.ConnectError:
        parsed_url = urlparse(url)
        raise click.ClickException(
            f"Llama Deploy is not responding, check the apiserver address {parsed_url.scheme}://{parsed_url.netloc} is correct and try again."
        )
