import asyncio
import time

from llama_deploy import (
    deploy_core,
)


async def run_deploy():
    await deploy_core(
        # All configs are optional.
        # In this case, the env vars in the docker-compose file are used.
        # control_plane_config=ControlPlaneConfig(),
        disable_message_queue=True,
    )


if __name__ == "__main__":
    # allow time for the messsage queue to spin up
    time.sleep(3)

    asyncio.run(run_deploy())
