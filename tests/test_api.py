from fastapi.testclient import TestClient

from relaylab.api import create_app


def test_api_validation_duplicates_and_persistence(tmp_path):
    database = tmp_path / "api.sqlite3"
    event = {"id": "evt-123", "event_type": "sensor.reading", "payload": {"value": 42}}
    with TestClient(create_app(database)) as client:
        assert client.get("/").status_code == 200
        assert client.post("/events", json=event).status_code == 201
        assert client.post("/events", json=event).status_code == 200
        assert client.post("/events", json={**event, "payload": {"value": 99}}).status_code == 409
        assert client.post("/events", json={"id": "broken"}).status_code == 422
        assert client.get("/events/missing").status_code == 404
        assert len(client.get("/events").json()) == 1
        assert client.get("/events/evt-123").json()["status"] == "pending"
    with TestClient(create_app(database)) as restarted:
        assert restarted.get("/events/evt-123").json()["payload"] == {"value": 42}


def test_demo_receiver():
    from relaylab.receiver import app, receipts
    receipts.clear()
    with TestClient(app) as client:
        event = {"id": "demo-1", "event_type": "sensor.reading", "payload": {"value": 42}}
        assert client.post("/webhook", json=event).status_code == 200
        assert client.get("/received").json() == [event]
        assert client.post("/fail").status_code == 503
    receipts.clear()
