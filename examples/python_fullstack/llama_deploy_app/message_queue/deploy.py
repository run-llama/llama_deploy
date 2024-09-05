import asyncio
from llama_deploy import (
    deploy_core,
)


async def run_deploy():
    await deploy_core(
        # All configs are optional.
        # In this case, the env vars in the docker-compose file are used.
        # message_queue_config=MessageQueueConfig(),
        disable_control_plane=True,
    )


if __name__ == "__main__":
    asyncio.run(run_deploy())
