from llama_deploy.message_queues.simple.config import SimpleMessageQueueConfig


def test_base_url() -> None:
    cfg = SimpleMessageQueueConfig()
    assert cfg.base_url == "http://127.0.0.1:8001/"
    cfg = SimpleMessageQueueConfig(port=80)
    assert cfg.base_url == "http://127.0.0.1/"
