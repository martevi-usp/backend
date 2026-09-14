from fastapi import APIRouter, Depends, HTTPException, Query

from martevi.api.deps import get_registry
from martevi.providers._internal.concurrency import gather_optional
from martevi.providers.base import MuseumProvider
from martevi.providers.fanout import fan_out_search
from martevi.schema import Artwork, ArtworkSummary, FanOutSearchResult, ProviderSearchStatus

router = APIRouter(prefix="/artworks", tags=["artworks"])


@router.get("", response_model=FanOutSearchResult)
async def search_artworks(
    q: str | None = Query(None, min_length=1),
    provider_id: str | None = Query(None),
    department: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    registry: dict[str, MuseumProvider] = Depends(get_registry),
) -> FanOutSearchResult:
    if provider_id is None:
        if q is None:
            raise HTTPException(400, "q is required when provider_id is omitted")
        if department is not None:
            raise HTTPException(400, "department requires provider_id")
        return await fan_out_search(registry, q, limit)

    provider = registry.get(provider_id)
    if provider is None:
        raise HTTPException(404, f"Unknown provider_id: {provider_id!r}")

    if q is None:
        # Query-less browse — a page of the collection, shown before anyone
        # searches. `department` filtering needs a search to filter, so it isn't
        # supported in browse mode.
        if department is not None:
            raise HTTPException(400, "department requires q")
        results = await provider.browse(limit, offset)
    elif department is None:
        results = await provider.search(q, limit)
    else:
        results = await _search_filtered_by_department(provider, q, limit, department)

    status = ProviderSearchStatus(provider_id=provider_id, ok=True, count=len(results))
    return FanOutSearchResult(results=results, provider_status=[status])


async def _search_filtered_by_department(
    provider: MuseumProvider, q: str, limit: int, department: str
) -> list[ArtworkSummary]:
    summaries = await provider.search(q, limit)
    artworks = await gather_optional(provider.get_item(s.id.split(":", 1)[1]) for s in summaries)
    target = department.casefold()
    return [a for a in artworks if a.department and a.department.casefold() == target]


@router.get("/{artwork_id}", response_model=Artwork)
async def get_artwork(
    artwork_id: str, registry: dict[str, MuseumProvider] = Depends(get_registry)
) -> Artwork:
    provider_id, sep, external_id = artwork_id.partition(":")
    if not sep:
        raise HTTPException(400, "id must be '{provider_id}:{external_id}'")

    provider = registry.get(provider_id)
    if provider is None:
        raise HTTPException(404, f"Unknown provider_id: {provider_id!r}")

    artwork = await provider.get_item(external_id)
    if artwork is None:
        raise HTTPException(404, f"Artwork not found: {artwork_id!r}")
    return artwork
