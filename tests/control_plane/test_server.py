from llama_deploy.control_plane import ControlPlaneServer
from llama_deploy.message_queues import SimpleMessageQueue


def test_control_plane_init() -> None:
    cp = ControlPlaneServer(SimpleMessageQueue())
    assert cp._orchestrator is not None
    assert cp._publish_callback is None
    assert cp._state_store is not None
    assert cp._config is not None
