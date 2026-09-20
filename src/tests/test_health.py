from fastapi.testclient import TestClient

from main import app


def test_health_answers_without_registry_database_or_network(monkeypatch, tmp_path):
    # No lifespan (so no provider registry on app.state) and no database file:
    # a probe that needed either would fail here.
    monkeypatch.setenv("MARTEVI_DB_PATH", str(tmp_path / "absent.db"))
    client = TestClient(app)  # not used as a context manager: lifespan never runs

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
