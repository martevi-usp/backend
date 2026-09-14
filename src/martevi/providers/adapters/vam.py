import httpx

from martevi.schema import Artwork, ArtworkSummary

_BASE = "https://api.vam.ac.uk/v2"
_IIIF_BASE = "https://framemark.vam.ac.uk/collections"


class VamProvider:
    """Victoria and Albert Museum Collections API v2. No key required."""

    provider_id = "vam"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def search(self, query: str, limit: int = 20) -> list[ArtworkSummary]:
        response = await self._client.get(
            f"{_BASE}/objects/search", params={"q": query, "page_size": limit}
        )
        response.raise_for_status()
        return [self._to_summary(item) for item in response.json().get("records") or []]

    async def browse(self, limit: int = 20, offset: int = 0) -> list[ArtworkSummary]:
        # V&A's search takes no query at all, and `images_exist` + page/page_size
        # is a real, native filter+pagination — no client-side reslicing needed.
        page = offset // limit + 1 if limit else 1
        response = await self._client.get(
            f"{_BASE}/objects/search",
            params={"images_exist": 1, "page": page, "page_size": limit},
        )
        response.raise_for_status()
        return [self._to_summary(item) for item in response.json().get("records") or []]

    async def get_item(self, external_id: str) -> Artwork | None:
        response = await self._client.get(f"{_BASE}/museumobject/{external_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
        record = payload.get("record")
        if record is None:
            return None
        return self._to_artwork(record, payload.get("meta") or {})

    def _to_summary(self, data: dict) -> ArtworkSummary:
        # `_images._primary_thumbnail` is a fixed 100x100 crop — real IIIF images
        # (same service get_item() below uses) are the same size class as every
        # other provider's search thumbnail, built from `_primaryImageId` instead.
        return ArtworkSummary(
            id=f"{self.provider_id}:{data['systemNumber']}",
            provider_id=self.provider_id,
            title=data.get("_primaryTitle") or "",
            date=data.get("_primaryDate") or None,
            thumbnail_url=self._thumbnail(data.get("_primaryImageId")),
            # V&A's search summaries carry no dimensions — an honest Optional gap,
            # not a bug. Fetch get_item() for dimensions.
            height_cm=None,
            width_cm=None,
        )

    def _to_artwork(self, record: dict, meta: dict) -> Artwork:
        height_cm, width_cm = self._dimensions_cm(record.get("dimensions") or [])
        # `record["images"]` is a bare list of image ids (e.g. ["2006AM6365"]), not
        # the `_images`/`_iiif_image` shape the search endpoint returns — a
        # previous version of this method read the wrong key entirely and always
        # got None here. Same IIIF service either way, keyed by image id.
        image_id = next(iter(record.get("images") or []), None)
        iiif_base = self._iiif_base(image_id)
        image_zoom_url = iiif_base
        image_url = f"{iiif_base}full/full/0/default.jpg" if iiif_base else None
        thumbnail_url = f"{iiif_base}full/400,/0/default.jpg" if iiif_base else image_url
        return Artwork(
            id=f"{self.provider_id}:{record['systemNumber']}",
            provider_id=self.provider_id,
            title=self._title(record),
            date=self._date(record),
            thumbnail_url=thumbnail_url,
            height_cm=height_cm,
            width_cm=width_cm,
            description=record.get("summaryDescription") or record.get("briefDescription") or None,
            medium=self._medium(record),
            culture=self._first_text(record.get("styles")),
            department=self._first_text(record.get("categories")),
            image_url=image_url,
            image_zoom_url=image_zoom_url,
            source_url=((meta.get("_links") or {}).get("collection_page") or {}).get("href"),
        )

    @staticmethod
    def _title(record: dict) -> str:
        for entry in record.get("titles") or []:
            if entry.get("type") == "generic title":
                return entry.get("title") or ""
        titles = record.get("titles") or []
        return titles[0].get("title") if titles else ""

    @staticmethod
    def _date(record: dict) -> str | None:
        dates = record.get("productionDates") or []
        if not dates:
            return None
        return (dates[0].get("date") or {}).get("text") or None

    @staticmethod
    def _dimensions_cm(dimensions: list[dict]) -> tuple[float | None, float | None]:
        height = width = None
        for entry in dimensions:
            if entry.get("unit") != "cm":
                continue
            if entry.get("dimension") == "Height":
                height = float(entry["value"])
            elif entry.get("dimension") == "Width":
                width = float(entry["value"])
        return height, width

    @staticmethod
    def _medium(record: dict) -> str | None:
        materials = [m.get("text") for m in record.get("materials") or [] if m.get("text")]
        return ", ".join(materials) or None

    @staticmethod
    def _first_text(entries: list[dict] | None) -> str | None:
        return entries[0].get("text") if entries else None

    @staticmethod
    def _iiif_base(image_id: str | None) -> str | None:
        return f"{_IIIF_BASE}/{image_id}/" if image_id else None

    @classmethod
    def _thumbnail(cls, image_id: str | None) -> str | None:
        base = cls._iiif_base(image_id)
        return f"{base}full/400,/0/default.jpg" if base else None
