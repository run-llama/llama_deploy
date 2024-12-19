from unittest import mock

import pytest

from llama_deploy.control_plane import ControlPlaneConfig, ControlPlaneServer
from llama_deploy.message_queues import SimpleMessageQueueServer


def test_control_plane_init() -> None:
    mq = SimpleMessageQueueServer()
    cp = ControlPlaneServer(mq)
    assert cp._orchestrator is not None
    assert cp._state_store is not None
    assert cp._config is not None

    assert cp.message_queue == mq
    assert cp.publisher_id.startswith("ControlPlaneServer-")
    assert cp.publish_callback is None

    assert cp.get_topic("msg_type") == "llama_deploy.msg_type"


def test_control_plane_init_state_store() -> None:
    mocked_store = mock.MagicMock()
    with pytest.raises(ValueError):
        ControlPlaneServer(
            SimpleMessageQueueServer(),
            state_store=mocked_store,
            config=ControlPlaneConfig(state_store_uri="test/uri"),
        )

    cp = ControlPlaneServer(SimpleMessageQueueServer(), state_store=mocked_store)
    assert cp._state_store == mocked_store

    with mock.patch(
        "llama_deploy.control_plane.server.parse_state_store_uri"
    ) as mocked_parse:
        ControlPlaneServer(
            SimpleMessageQueueServer(),
            config=ControlPlaneConfig(state_store_uri="test/uri"),
        )
        mocked_parse.assert_called_with("test/uri")
