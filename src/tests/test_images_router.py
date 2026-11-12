import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from martevi.api.deps import get_http_client
from martevi.api.images import router

_ID = "e966799b-97ee-1cc6-bd2f-a94b4b8bb8f9"
_UPSTREAM = f"https://www.artic.edu/iiif/2/{_ID}/full/200,/0/default.jpg"


@pytest.fixture
def client(respx_mock):
    app = FastAPI()
    app.include_router(router)
    http_client = httpx.AsyncClient()
    app.dependency_overrides[get_http_client] = lambda: http_client
    return TestClient(app)


def test_proxies_the_image_with_the_aic_user_agent(respx_mock, client, monkeypatch):
    monkeypatch.setenv("AIC_USER_AGENT", "martevi-test (test@example.org)")
    route = respx_mock.get(_UPSTREAM).mock(
        return_value=httpx.Response(200, content=b"jpegbytes")
    )

    response = client.get(f"/images/aic/{_ID}/full/200,/0/default.jpg")

    assert response.status_code == 200
    assert response.content == b"jpegbytes"
    assert response.headers["content-type"] == "image/jpeg"
    assert "max-age" in response.headers["cache-control"]
    assert route.calls.last.request.headers["AIC-User-Agent"] == "martevi-test (test@example.org)"


@pytest.mark.parametrize(
    "path",
    [
        "/images/aic/not-an-id/full/200,/0/default.jpg",
        f"/images/aic/{_ID}/0,0,10,10/200,/0/default.jpg",
        f"/images/aic/{_ID}/full/200,/0/evil.jpg",
        f"/images/aic/{_ID}/full/99999999,/0/default.jpg",
    ],
)
def test_rejects_anything_outside_the_allow_list_without_calling_upstream(
    respx_mock, client, path
):
    response = client.get(path)

    assert response.status_code == 404
    assert respx_mock.calls.call_count == 0


def test_upstream_failure_is_a_502(respx_mock, client):
    respx_mock.get(_UPSTREAM).mock(return_value=httpx.Response(403))

    assert client.get(f"/images/aic/{_ID}/full/200,/0/default.jpg").status_code == 502
