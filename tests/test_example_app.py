import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from tests.example_app.main import app


@pytest.fixture(scope="function")
def client():
    with TestClient(app) as client:
        yield client


def test_read_asyncapi_docs(client: TestClient):
    response = client.get("/asyncapi.json")
    assert response.status_code == 200
    response = client.get("/asyncapi")
    assert response.status_code == 200


def test_websocket(client: TestClient):
    with client.websocket_connect("/?topic=foo&topic=bar") as websocket:
        websocket.send_json({"type": "ping"}, mode="text")
        data = websocket.receive_json()
        assert data == {"type": "pong"}

        websocket.send_json(
            {"type": "feature_0.subscribe", "payload": {"topic": "foobar"}},
            mode="text",
        )
        data = websocket.receive_json()
        assert "type" in data and data["type"] == "feature_0.subscribe.response"
        assert "payload" in data and "topics" in data["payload"]
        assert set(data["payload"]["topics"]) == set(["foo", "foobar", "bar"])

        websocket.send_json({"type": "feature_1.ping"}, mode="text")
        data = websocket.receive_json()
        assert data == {"type": "feature_1.pong"}

        response = client.post("/foobar")
        assert response.status_code == 200

        data = websocket.receive_json()
        assert data == {"type": "feature_2.alert", "payload": {"message": "foobar"}}

        websocket.send_json(
            {"type": "feature_0.not_an_operation", "payload": {"foo": "bar"}},
            mode="text",
        )
        with pytest.raises(WebSocketDisconnect, match="No matching type") as exc_info:
            websocket.receive_json()
        assert exc_info.value.code == 1003
