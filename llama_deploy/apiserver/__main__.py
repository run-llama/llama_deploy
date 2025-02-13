import uvicorn
from prometheus_client import start_http_server

from .settings import ApiserverSettings

if __name__ == "__main__":
    settings = ApiserverSettings()

    if settings.prometheus_enabled:
        start_http_server(settings.prometheus_port)

    uvicorn.run(
        "llama_deploy.apiserver:app",
        host=settings.host,
        port=settings.port,
    )
