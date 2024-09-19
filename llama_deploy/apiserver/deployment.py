from pathlib import Path

from llama_deploy import (
    ControlPlaneServer,
    SimpleMessageQueue,
    SimpleMessageQueueConfig,
    SimpleOrchestratorConfig,
    SimpleOrchestrator,
)

from .config_parser import Config

DEPLOYMENTS_ROOT = Path(".deployments")


class Deployment:
    def __init__(self, config: Config) -> None:
        self._name = config.name
        self._path: Path = DEPLOYMENTS_ROOT / self._name

        # TODO: make it configurable
        mq = SimpleMessageQueue(**SimpleMessageQueueConfig().model_dump())
        mq_client = mq.client

        self._control_plane = ControlPlaneServer(
            mq_client,
            SimpleOrchestrator(**SimpleOrchestratorConfig().model_dump()),
            **config.control_plane.model_dump(),
        )
