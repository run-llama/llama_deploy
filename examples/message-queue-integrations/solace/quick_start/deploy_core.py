from dotenv import load_dotenv, find_dotenv

from llama_deploy.deploy.deploy import (
    deploy_core,
    ControlPlaneConfig,
    SolaceMessageQueueConfig,
)


def load_env():
    # Load environment variables from .env.solace file
    dotenv_path = find_dotenv(".env.solace")
    if not dotenv_path:
        raise FileNotFoundError(".env.solace file not found")

    load_dotenv(dotenv_path)


async def main():
    await deploy_core(
        control_plane_config=ControlPlaneConfig(),
        message_queue_config=SolaceMessageQueueConfig(),
    )


if __name__ == "__main__":
    import asyncio

    load_env()
    asyncio.run(main())
