import asyncio
from llama_deploy import (
    ControlPlaneConfig,
    SimpleMessageQueueConfig,
    deploy_core,
)


async def run_deploy():
    await deploy_core(
        control_plane_config=ControlPlaneConfig(host="0.0.0.0", port=8000),
        message_queue_config=SimpleMessageQueueConfig(host="0.0.0.0", port=8001),
    )


if __name__ == "__main__":
    asyncio.run(run_deploy())
