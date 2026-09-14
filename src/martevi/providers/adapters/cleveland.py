import httpx

from martevi.schema import Artwork, ArtworkSummary

_BASE = "https://openaccess-api.clevelandart.org/api"


class ClevelandProvider:
    """Cleveland Museum of Art Open Access API. No key required; no documented rate
    limit — self-throttle defensively regardless."""

    provider_id = "cleveland"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def search(self, query: str, limit: int = 20) -> list[ArtworkSummary]:
        response = await self._client.get(f"{_BASE}/artworks/", params={"q": query, "limit": limit})
        response.raise_for_status()
        return [self._to_artwork(item) for item in response.json().get("data") or []]

    async def browse(self, limit: int = 20, offset: int = 0) -> list[ArtworkSummary]:
        # Cleveland's plain /artworks/ listing needs no query at all, and takes a
        # real has_image filter plus skip/limit offset pagination natively.
        response = await self._client.get(
            f"{_BASE}/artworks/", params={"has_image": 1, "skip": offset, "limit": limit}
        )
        response.raise_for_status()
        return [self._to_artwork(item) for item in response.json().get("data") or []]

    async def get_item(self, external_id: str) -> Artwork | None:
        response = await self._client.get(f"{_BASE}/artworks/{external_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json().get("data")
        if data is None:
            return None
        return self._to_artwork(data)

    def _to_artwork(self, data: dict) -> Artwork:
        height_cm, width_cm = self._dimensions_cm(data.get("dimensions") or {})
        images = data.get("images") or {}
        image_url = (images.get("print") or {}).get("url") or None
        culture = data.get("culture") or []
        return Artwork(
            id=f"{self.provider_id}:{data['id']}",
            provider_id=self.provider_id,
            title=data.get("title") or "",
            date=data.get("creation_date") or None,
            thumbnail_url=image_url,
            height_cm=height_cm,
            width_cm=width_cm,
            description=data.get("description") or None,
            medium=data.get("technique") or None,
            culture=culture[0] if culture else None,
            department=data.get("department") or None,
            image_url=image_url,
            image_zoom_url=None,
            source_url=data.get("url") or None,
        )

    @staticmethod
    def _dimensions_cm(dimensions: dict) -> tuple[float | None, float | None]:
        part = dimensions.get("unframed") or next(iter(dimensions.values()), None)
        if not part:
            return None, None
        height = part.get("height")
        width = part.get("width")
        # Cleveland reports dimensions in meters, not cm.
        return (height * 100 if height is not None else None), (
            width * 100 if width is not None else None
        )
