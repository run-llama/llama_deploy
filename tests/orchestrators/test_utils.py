from llama_deploy.orchestrators.utils import get_result_key, get_stream_key


def test_get_result_key() -> None:
    assert get_result_key("test_task") == "result_test_task"


def test_get_stream_key() -> None:
    assert get_stream_key("test_task") == "stream_test_task"
