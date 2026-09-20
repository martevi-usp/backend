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


def test_cors_origin_regex_allows_matching_subdomains(monkeypatch):
    import importlib

    import main

    monkeypatch.setenv(
        "CORS_ORIGIN_REGEX", r"https://([a-z0-9-]+-)?frontend\.gio-uchoa\.workers\.dev"
    )
    reloaded = importlib.reload(main)
    try:
        with TestClient(reloaded.app) as client:
            def acao(origin):
                return client.options(
                    "/artworks",
                    headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
                ).headers.get("access-control-allow-origin")

            preview = "https://e225b38a-frontend.gio-uchoa.workers.dev"
            assert acao(preview) == preview
            assert acao("https://frontend.gio-uchoa.workers.dev.evil.com") is None
            assert acao("https://x-frontend.other.workers.dev") is None
    finally:
        monkeypatch.delenv("CORS_ORIGIN_REGEX")
        importlib.reload(main)
