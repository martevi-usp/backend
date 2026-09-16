import httpx

from martevi.providers._internal.dimensions import parse_positional
from martevi.schema import Artwork, ArtworkSummary

_BASE = "https://api.si.edu/openaccess/api/v1.0"


class SmithsonianProvider:
    """Smithsonian Open Access API (EDAN). Works with the shared DEMO_KEY
    (~30 req/hr/IP); a free api.data.gov key raises that to 1000/hr."""

    provider_id = "smithsonian"

    def __init__(self, client: httpx.AsyncClient, api_key: str) -> None:
        self._client = client
        self._api_key = api_key

    async def search(self, query: str, limit: int = 20) -> list[ArtworkSummary]:
        response = await self._client.get(
            f"{_BASE}/search",
            params={"q": query, "api_key": self._api_key, "rows": limit},
        )
        response.raise_for_status()
        rows = (response.json().get("response") or {}).get("rows") or []
        return [self._to_artwork(row) for row in rows]

    async def browse(self, limit: int = 20, offset: int = 0) -> list[ArtworkSummary]:
        # EDAN's `q` is required (empty/missing 400s) but a single common letter
        # matches virtually the whole collection (confirmed live: ~2.8M rows) —
        # `start` is EDAN's real, native offset, confirmed to shift the window.
        response = await self._client.get(
            f"{_BASE}/search",
            params={"q": "a", "api_key": self._api_key, "rows": limit, "start": offset},
        )
        response.raise_for_status()
        rows = (response.json().get("response") or {}).get("rows") or []
        return [self._to_artwork(row) for row in rows]

    async def get_item(self, external_id: str) -> Artwork | None:
        response = await self._client.get(
            f"{_BASE}/content/{external_id}", params={"api_key": self._api_key}
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json().get("response")
        if data is None:
            return None
        return self._to_artwork(data)

    def _to_artwork(self, data: dict) -> Artwork:
        content = data.get("content") or {}
        descriptive = content.get("descriptiveNonRepeating") or {}
        freetext = content.get("freetext") or {}
        indexed = content.get("indexedStructured") or {}
        media_items = (descriptive.get("online_media") or {}).get("media") or []

        title = (descriptive.get("title") or {}).get("content") or data.get("title") or ""
        height_cm, width_cm = self._dimensions_cm(freetext.get("physicalDescription") or [])
        image_url, thumbnail_url = self._images(media_items)
        culture = indexed.get("culture") or []

        return Artwork(
            id=f"{self.provider_id}:{data['id']}",
            provider_id=self.provider_id,
            title=title,
            date=self._first(freetext.get("date")),
            thumbnail_url=thumbnail_url,
            height_cm=height_cm,
            width_cm=width_cm,
            description=None,
            medium=self._labeled(freetext.get("physicalDescription") or [], "Medium"),
            culture=culture[0] if culture else None,
            department=self._labeled(freetext.get("setName") or [], "Department"),
            image_url=image_url,
            image_zoom_url=self._iiif_manifest(media_items),
            source_url=descriptive.get("record_link") or None,
        )

    @staticmethod
    def _first(entries: list[dict] | None) -> str | None:
        return entries[0].get("content") if entries else None

    @staticmethod
    def _labeled(entries: list[dict], label: str) -> str | None:
        for entry in entries:
            if entry.get("label") == label:
                return entry.get("content") or None
        return None

    @classmethod
    def _dimensions_cm(cls, entries: list[dict]) -> tuple[float | None, float | None]:
        for entry in entries:
            content = entry.get("content")
            height, width = parse_positional(content)
            if height is not None and width is not None:
                return height, width
        return None, None

    @staticmethod
    def _images(media_items: list[dict]) -> tuple[str | None, str | None]:
        if not media_items:
            return None, None
        resources = media_items[0].get("resources") or []
        image_url = next(
            (r.get("url") for r in resources if r.get("label") == "Screen Image"), None
        )
        # EDAN's own "Thumbnail Image" resource is a genuinely tiny crop
        # (~150px) meant for a small icon, not a masonry grid card that can
        # be 300px+ wide — using it as `thumbnail_url` made every Smithsonian
        # card look blurry/pixelated. "Screen Image" (the same one used for
        # `image_url`) is a much larger web-sized image and renders sharp at
        # grid size; only fall back to the small thumbnail if that's all a
        # record has.
        thumbnail_url = (
            image_url
            or next((r.get("url") for r in resources if r.get("label") == "Thumbnail Image"), None)
            or media_items[0].get("thumbnail")
        )
        return image_url, thumbnail_url

    @staticmethod
    def _iiif_manifest(media_items: list[dict]) -> str | None:
        if not media_items:
            return None
        ids_id = media_items[0].get("idsId")
        return f"https://ids.si.edu/ids/manifest/{ids_id}" if ids_id else None
