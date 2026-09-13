from fastapi.testclient import TestClient

from main import app


def test_cors_allows_the_frontend_dev_origin():
    with TestClient(app) as client:
        response = client.options(
            "/artworks",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_rejects_an_unlisted_origin():
    with TestClient(app) as client:
        response = client.options(
            "/artworks",
            headers={
                "Origin": "http://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert "access-control-allow-origin" not in response.headers
