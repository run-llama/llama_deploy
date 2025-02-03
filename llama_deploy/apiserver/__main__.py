import uvicorn

from .settings import ApiserverSettings

if __name__ == "__main__":
    settings = ApiserverSettings()
    uvicorn.run(
        "llama_deploy.apiserver:app",
        host=settings.host,
        port=settings.port,
    )
