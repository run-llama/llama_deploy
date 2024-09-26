from fastapi.testclient import TestClient


def test_read_main(http_client: TestClient) -> None:
    response = http_client.get("/status")
    assert response.status_code == 200
    assert response.json() == {
        "max_deployments": 10,
        "deployments": [],
        "status": "Up!",
    }
