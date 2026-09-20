from typing import Annotated

from fastapi import APIRouter, Depends

from martevi.api.deps import get_tour_link_repository
from martevi.repositories import TourLinkRepository
from martevi.schema.puzzle import TourLinkOut

router = APIRouter(tags=["Tours"])


@router.get("/tours", response_model=list[TourLinkOut])
def list_tours(
    repo: Annotated[TourLinkRepository, Depends(get_tour_link_repository)],
    museum: str | None = None,
) -> list[dict]:
    """Curated virtual-tour links, optionally for one museum."""
    return [
        {"id": t.id, "museum": t.museum, "country": t.country, "title": t.title, "url": t.url}
        for t in repo.list_all(museum)
    ]
