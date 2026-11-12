import os

import httpx

from martevi.schema import Artwork, ArtworkSummary

_BASE = "https://api.artic.edu/api/v1"
_SEARCH_FIELDS = "id,title,date_display,image_id,dimensions_detail"
# AIC asks API users to identify themselves with this header (ideally with a
# contact address); set AIC_USER_AGENT to override the default.
_DEFAULT_AIC_USER_AGENT = "martevi-backend/0.1 (educational museum project)"
_ITEM_FIELDS = (
    "id,title,date_display,dimensions_detail,medium_display,department_title,"
    "short_description,description,image_id"
)


def aic_headers() -> dict[str, str]:
    """Identifying header AIC requires — on its API and on its IIIF image server."""
    return {"AIC-User-Agent": os.environ.get("AIC_USER_AGENT") or _DEFAULT_AIC_USER_AGENT}


class AicProvider:
    """Art Institute of Chicago API. No key required; self-throttle ~1 req/s."""

    provider_id = "aic"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._headers = aic_headers()

    async def search(self, query: str, limit: int = 20) -> list[ArtworkSummary]:
        response = await self._client.get(
            f"{_BASE}/artworks/search",
            params={"q": query, "limit": limit, "fields": _SEARCH_FIELDS},
            headers=self._headers,
        )
        response.raise_for_status()
        payload = response.json()
        iiif_url = (payload.get("config") or {}).get("iiif_url")
        return [self._to_summary(item, iiif_url) for item in payload.get("data") or []]

    async def browse(self, limit: int = 20, offset: int = 0) -> list[ArtworkSummary]:
        # AIC's plain /artworks listing is a real paginated "browse everything" —
        # no query needed at all (unlike /artworks/search). It has no has-image
        # filter param of its own, so items without one are dropped client-side.
        page = offset // limit + 1 if limit else 1
        response = await self._client.get(
            f"{_BASE}/artworks",
            params={"page": page, "limit": limit, "fields": _SEARCH_FIELDS},
            headers=self._headers,
        )
        response.raise_for_status()
        payload = response.json()
        iiif_url = (payload.get("config") or {}).get("iiif_url")
        return [
            self._to_summary(item, iiif_url)
            for item in payload.get("data") or []
            if item.get("image_id")
        ]

    async def get_item(self, external_id: str) -> Artwork | None:
        response = await self._client.get(
            f"{_BASE}/artworks/{external_id}",
            params={"fields": _ITEM_FIELDS},
            headers=self._headers,
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
        # AIC's image server only answers requests carrying the AIC-User-Agent
        # header, which a browser <img> can't send — so displayable image URLs
        # point at our own /images/aic proxy (relative; the client resolves them
        # against the API base). The IIIF base stays upstream for deep-zoom use.
        proxy = f"/images/aic/{image_id}"
        return (
            f"{proxy}/full/full/0/default.jpg",
            f"{proxy}/full/200,/0/default.jpg",
            f"{iiif_url}/{image_id}",
        )
