import httpx

from martevi.providers._internal.dimensions import parse_labeled
from martevi.providers._internal.text import blank_to_none
from martevi.schema import Artwork, ArtworkSummary

# Harvard Art Museums API: non-commercial use only, 2500 requests/day, and content
# may not be cached/stored for more than two weeks without written permission.
_BASE = "https://api.harvardartmuseums.org"
_FIELDS = (
    "id,objectnumber,title,dated,primaryimageurl,dimensions,culture,period,"
    "department,medium,url,description,labeltext,commentary,contextualtext,"
    "seeAlso,images"
)


class HarvardProvider:
    """Harvard Art Museums API. Requires a free, non-commercial API key."""

    provider_id = "harvard"

    def __init__(self, client: httpx.AsyncClient, api_key: str) -> None:
        self._client = client
        self._api_key = api_key

    async def search(self, query: str, limit: int = 20) -> list[ArtworkSummary]:
        response = await self._client.get(
            f"{_BASE}/object",
            params={"keyword": query, "size": limit, "apikey": self._api_key, "fields": _FIELDS},
        )
        response.raise_for_status()
        return [self._to_artwork(item) for item in response.json().get("records") or []]

    async def browse(self, limit: int = 20, offset: int = 0) -> list[ArtworkSummary]:
        # No confirmed native offset for this adapter (untestable without a working
        # API key), so delegate to search() with a broad keyword and reslice —
        # correct, just costlier than a real offset for deep pages.
        results = await self.search("a", limit=offset + limit)
        return results[offset:]

    async def get_item(self, external_id: str) -> Artwork | None:
        response = await self._client.get(
            f"{_BASE}/object/{external_id}", params={"apikey": self._api_key}
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return self._to_artwork(response.json())

    def _to_artwork(self, data: dict) -> Artwork:
        height_cm, width_cm = parse_labeled(
            data.get("dimensions"),
            height_labels=("h.", "height"),
            width_labels=("w.", "width"),
        )
        image_url, thumbnail_url = self._images(data)
        return Artwork(
            id=f"{self.provider_id}:{data['id']}",
            provider_id=self.provider_id,
            title=data.get("title") or "",
            date=data.get("dated") or None,
            thumbnail_url=thumbnail_url,
            height_cm=height_cm,
            width_cm=width_cm,
            description=self._description(data),
            medium=data.get("medium") or None,
            culture=blank_to_none(data.get("culture")) or blank_to_none(data.get("period")),
            department=data.get("department") or None,
            image_url=image_url,
            image_zoom_url=self._iiif_manifest(data),
            source_url=data.get("url") or None,
        )

    @staticmethod
    def _description(data: dict) -> str | None:
        for field in ("labeltext", "description", "commentary"):
            value = blank_to_none(data.get(field))
            if value:
                return value
        for entry in data.get("contextualtext") or []:
            value = blank_to_none(entry.get("text"))
            if value:
                return value
        return None

    @staticmethod
    def _images(data: dict) -> tuple[str | None, str | None]:
        base = data.get("primaryimageurl")
        if not base:
            images = data.get("images") or []
            base = images[0].get("baseimageurl") if images else None
        if not base:
            return None, None
        return f"{base}/full/full/0/default.jpg", f"{base}/full/200,/0/default.jpg"

    @staticmethod
    def _iiif_manifest(data: dict) -> str | None:
        for entry in data.get("seeAlso") or []:
            if entry.get("type") == "IIIF Manifest":
                return entry.get("id")
        return None
