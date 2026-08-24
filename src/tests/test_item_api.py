from fastapi import FastAPI
from fastapi.testclient import TestClient

from martevi.api import item_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(item_router)
    return TestClient(app)


def test_item_routes_registered():
    openapi = _client().get("/openapi.json").json()
    assert {"/items", "/items/{item_id}"} <= openapi["paths"].keys()


def test_docs_available():
    response = _client().get("/docs")
    assert response.status_code == 200
