import httpx

from martevi.schema import Artwork, ArtworkSummary

_BASE = "https://api.artic.edu/api/v1"
_SEARCH_FIELDS = "id,title,date_display,image_id,dimensions_detail"
_ITEM_FIELDS = (
    "id,title,date_display,dimensions_detail,medium_display,department_title,"
    "short_description,description,image_id"
)


class AicProvider:
    """Art Institute of Chicago API. No key required; self-throttle ~1 req/s."""

    provider_id = "aic"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def search(self, query: str, limit: int = 20) -> list[ArtworkSummary]:
        response = await self._client.get(
            f"{_BASE}/artworks/search",
            params={"q": query, "limit": limit, "fields": _SEARCH_FIELDS},
        )
        response.raise_for_status()
        payload = response.json()
        iiif_url = (payload.get("config") or {}).get("iiif_url")
        return [self._to_summary(item, iiif_url) for item in payload.get("data") or []]

    async def get_item(self, external_id: str) -> Artwork | None:
        response = await self._client.get(
            f"{_BASE}/artworks/{external_id}", params={"fields": _ITEM_FIELDS}
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
        iiif_url = (payload.get("config") or {}).get("iiif_url")
        return self._to_artwork(payload.get("data") or {}, iiif_url)

    def _to_summary(self, data: dict, iiif_url: str | None) -> ArtworkSummary:
        height_cm, width_cm = self._dimensions_cm(data)
        _, thumbnail_url, _ = self._images(data, iiif_url)
        return ArtworkSummary(
            id=f"{self.provider_id}:{data['id']}",
            provider_id=self.provider_id,
            title=data.get("title") or "",
            date=data.get("date_display") or None,
            thumbnail_url=thumbnail_url,
            height_cm=height_cm,
            width_cm=width_cm,
        )

    def _to_artwork(self, data: dict, iiif_url: str | None) -> Artwork:
        height_cm, width_cm = self._dimensions_cm(data)
        image_url, thumbnail_url, image_zoom_url = self._images(data, iiif_url)
        description = data.get("short_description") or data.get("description") or None
        return Artwork(
            id=f"{self.provider_id}:{data['id']}",
            provider_id=self.provider_id,
            title=data.get("title") or "",
            date=data.get("date_display") or None,
            thumbnail_url=thumbnail_url,
            height_cm=height_cm,
            width_cm=width_cm,
            description=description,
            medium=data.get("medium_display") or None,
            culture=None,
            department=data.get("department_title") or None,
            image_url=image_url,
            image_zoom_url=image_zoom_url,
            # Not returned as a field by AIC's API — constructed from AIC's own
            # stable, documented public object-page URL scheme.
            source_url=f"https://www.artic.edu/artworks/{data['id']}",
        )

    @staticmethod
    def _dimensions_cm(data: dict) -> tuple[float | None, float | None]:
        details = data.get("dimensions_detail") or []
        if not details:
            return None, None
        return details[0].get("height"), details[0].get("width")

    @staticmethod
    def _images(
        data: dict, iiif_url: str | None
    ) -> tuple[str | None, str | None, str | None]:
        image_id = data.get("image_id")
        if not image_id or not iiif_url:
            return None, None, None
        base = f"{iiif_url}/{image_id}"
        return f"{base}/full/full/0/default.jpg", f"{base}/full/200,/0/default.jpg", base
