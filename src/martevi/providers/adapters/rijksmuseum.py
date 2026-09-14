import httpx

from martevi.providers._internal.concurrency import gather_optional
from martevi.providers._internal.dimensions import parse_labeled
from martevi.schema import Artwork, ArtworkSummary

_SEARCH_BASE = "https://data.rijksmuseum.nl"
_RESOLVE_BASE = "https://id.rijksmuseum.nl"
_IIIF_SERVICE = "http://rdfs.org/sioc/services#has_service"


class RijksmuseumProvider:
    """Rijksmuseum's new Linked Open Data API (data.rijksmuseum.nl). No key required
    — the legacy keyed Collection API was fully shut down in January 2026."""

    provider_id = "rijksmuseum"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def search(self, query: str, limit: int = 20) -> list[ArtworkSummary]:
        # NOTE: search returns bare Linked Data ids only, no summary data — every
        # result needs a full get_item() call. Caching is out of scope per ADR-0001.
        response = await self._client.get(
            f"{_SEARCH_BASE}/search/collection", params={"title": query}
        )
        response.raise_for_status()
        items = response.json().get("orderedItems") or []
        external_ids = [item["id"].rsplit("/", 1)[-1] for item in items[:limit]]
        return await gather_optional(self.get_item(eid) for eid in external_ids)

    async def browse(self, limit: int = 20, offset: int = 0) -> list[ArtworkSummary]:
        # The new Linked Art API paginates via opaque pageTokens in its response
        # (`next`/`last` links), not a numeric offset, and a blank `title` matches
        # nothing (confirmed live: 0 results) — not worth a bespoke cursor
        # abstraction for one adapter. "de" (Dutch "the/of") matches ~206k objects,
        # broad enough to browse; delegate to search() and reslice.
        results = await self.search("de", limit=offset + limit)
        return results[offset:]

    async def get_item(self, external_id: str) -> Artwork | None:
        response = await self._client.get(
            f"{_RESOLVE_BASE}/{external_id}", params={"_profile": "edm-framed"}
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return self._to_artwork(external_id, response.json())

    def _to_artwork(self, external_id: str, data: dict) -> Artwork:
        cho = data.get("aggregatedCHO") or {}
        height_cm, width_cm = self._dimensions_cm(cho.get("extent") or [])
        image_url = (data.get("isShownBy") or {}).get("id") or None
        image_zoom_url = ((data.get("isShownBy") or {}).get(_IIIF_SERVICE) or {}).get("id") or None
        return Artwork(
            id=f"{self.provider_id}:{external_id}",
            provider_id=self.provider_id,
            title=self._localized(cho.get("title") or {}) or "",
            date=self._localized_value(cho.get("created") or []),
            thumbnail_url=self._thumbnail(image_zoom_url, image_url),
            height_cm=height_cm,
            width_cm=width_cm,
            description=None,
            medium=self._medium(cho.get("medium") or []),
            culture=None,
            department=None,
            image_url=image_url,
            image_zoom_url=image_zoom_url,
            source_url=(data.get("isShownAt") or {}).get("id") or None,
        )

    @staticmethod
    def _localized(labels: dict) -> str | None:
        return labels.get("en") or labels.get("nl") or next(iter(labels.values()), None)

    @staticmethod
    def _localized_value(entries: list[dict]) -> str | None:
        for entry in entries:
            if entry.get("@language") == "en":
                return entry.get("@value")
        return entries[0].get("@value") if entries else None

    @staticmethod
    def _dimensions_cm(extent: list[dict]) -> tuple[float | None, float | None]:
        text = None
        for entry in extent:
            if entry.get("@language") == "en":
                text = entry.get("@value")
                break
        if text is None and extent:
            text = extent[0].get("@value")
        return parse_labeled(
            text, height_labels=("height",), width_labels=("width",), default_unit="mm"
        )

    @staticmethod
    def _medium(medium: list[dict]) -> str | None:
        labels = []
        for concept in medium:
            pref_labels = concept.get("http://www.w3.org/2004/02/skos/core#prefLabel") or []
            if isinstance(pref_labels, dict):
                pref_labels = [pref_labels]
            for label in pref_labels:
                value = label.get("@value")
                if value:
                    labels.append(value)
        return ", ".join(labels) or None

    @staticmethod
    def _thumbnail(image_zoom_url: str | None, image_url: str | None) -> str | None:
        if image_zoom_url:
            return f"{image_zoom_url}/full/200,/0/default.jpg"
        return image_url
