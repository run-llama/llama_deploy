from llama_deploy import (
    ControlPlaneConfig,
    ControlPlaneServer,
    SimpleMessageQueue,
    SimpleMessageQueueConfig,
    SimpleOrchestrator,
    SimpleOrchestratorConfig,
)


def test_message_type() -> None:
    mq = SimpleMessageQueue(**SimpleMessageQueueConfig().model_dump())
    cfg = ControlPlaneConfig(message_type="foo")
    control_plane = ControlPlaneServer(
        mq.client,
        SimpleOrchestrator(**SimpleOrchestratorConfig().model_dump()),
        **cfg.model_dump(),
    )
    consumer = control_plane.as_consumer(remote=False)
    assert consumer.message_type == "foo"
    consumer = control_plane.as_consumer(remote=True)
    assert consumer.message_type == "foo"
