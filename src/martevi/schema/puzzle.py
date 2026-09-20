from pydantic import BaseModel


class StoryOut(BaseModel):
    lede: str
    body: str
    unlock_pct: int


class PuzzleOut(BaseModel):
    id: str
    title: str
    credit: str
    src: str
    rights: str
    verified: bool
    movement: str
    pieces: int


class PuzzleDetailOut(PuzzleOut):
    """Stories appear only once `progress_pct` reaches their unlock point.
    The client reports its own progress (no auth), so this is a courtesy
    against casual spoilers, not a guarantee — see ADR-0004."""

    stories: list[StoryOut]


class TourLinkOut(BaseModel):
    id: int
    museum: str
    country: str | None
    title: str
    url: str
