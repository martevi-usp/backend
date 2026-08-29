import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from martevi.api import artworks_router
from martevi.api.deps import get_registry
from martevi.providers.base import MuseumProvider
from martevi.schema import Artwork, ArtworkSummary


class FakeProvider:
    """In-memory MuseumProvider test double: canned summaries/items for search()/
    get_item(), or an injected error for fan-out/router failure-path tests."""

    def __init__(
        self,
        provider_id: str,
        summaries: list[ArtworkSummary] | None = None,
        items: dict[str, Artwork] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.provider_id = provider_id
        self._summaries = summaries or []
        self._items = items or {}
        self._error = error

    async def search(self, query: str, limit: int = 20) -> list[ArtworkSummary]:
        if self._error is not None:
            raise self._error
        return self._summaries[:limit]

    async def get_item(self, external_id: str) -> Artwork | None:
        return self._items.get(external_id)


class FakeTranslator:
    """Deterministic test double: prefixes text so tests can assert exactly what was
    translated, and records every call it received."""

    def __init__(self, prefix: str = "PT::") -> None:
        self._prefix = prefix
        self.calls: list[str] = []

    async def translate(self, text: str) -> str:
        self.calls.append(text)
        return f"{self._prefix}{text}"


@pytest.fixture
async def async_client():
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def make_test_client():
    """Factory fixture: builds a TestClient for the /artworks router with the given
    provider registry overriding the real get_registry dependency."""

    def _make(registry: dict[str, MuseumProvider]) -> TestClient:
        app = FastAPI()
        app.include_router(artworks_router)
        app.dependency_overrides[get_registry] = lambda: registry
        return TestClient(app)

    return _make
