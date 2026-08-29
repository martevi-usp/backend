import httpx

from martevi.providers._internal.concurrency import gather_optional
from martevi.providers._internal.text import blank_to_none
from martevi.schema import Artwork, ArtworkSummary

_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"


class MetProvider:
    """Metropolitan Museum of Art Collection API. No key required."""

    provider_id = "met"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def search(self, query: str, limit: int = 20) -> list[ArtworkSummary]:
        # NOTE: Met's search endpoint returns object IDs only, no summary data — every
        # result needs a full get_item() call. Caching is out of scope per ADR-0001.
        response = await self._client.get(f"{_BASE}/search", params={"q": query})
        response.raise_for_status()
        object_ids = response.json().get("objectIDs") or []
        return await gather_optional(
            (self.get_item(str(object_id)) for object_id in object_ids[:limit]),
        )

    async def get_item(self, external_id: str) -> Artwork | None:
        response = await self._client.get(f"{_BASE}/objects/{external_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return self._to_artwork(response.json())

    def _to_artwork(self, data: dict) -> Artwork:
        object_id = str(data["objectID"])
        height_cm, width_cm = self._dimensions_cm(data.get("measurements") or [])
        image_url = data.get("primaryImage") or None
        return Artwork(
            id=f"{self.provider_id}:{object_id}",
            provider_id=self.provider_id,
            title=data.get("title") or "",
            date=data.get("objectDate") or None,
            thumbnail_url=image_url,
            height_cm=height_cm,
            width_cm=width_cm,
            description=None,
            medium=data.get("medium") or None,
            culture=blank_to_none(data.get("culture")),
            department=data.get("department") or None,
            image_url=image_url,
            image_zoom_url=None,
            source_url=data.get("objectURL") or None,
        )

    @staticmethod
    def _dimensions_cm(measurements: list[dict]) -> tuple[float | None, float | None]:
        for element in measurements:
            if element.get("elementName") == "Overall":
                values = element.get("elementMeasurements") or {}
                return values.get("Height"), values.get("Width")
        return None, None
