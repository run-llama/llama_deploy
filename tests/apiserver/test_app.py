from fastapi.testclient import TestClient


def test_read_main(http_client: TestClient) -> None:
    response = http_client.get("/")
    assert response.status_code == 200
    assert set(response.json().keys()) == {"swagger_docs", "status"}
