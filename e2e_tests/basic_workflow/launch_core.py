from llama_deploy import deploy_core, ControlPlaneConfig, SimpleMessageQueueConfig


async def main():
    await deploy_core(
        ControlPlaneConfig(),
        SimpleMessageQueueConfig(),
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
