from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from martevi.api.deps import get_puzzle_repository
from martevi.repositories import PuzzleRepository
from martevi.schema.puzzle import PuzzleDetailOut, PuzzleOut, StoryOut

router = APIRouter(tags=["Puzzles"])

Repo = Annotated[PuzzleRepository, Depends(get_puzzle_repository)]


def _out(p) -> dict:
    return {
        "id": p.id, "title": p.title, "credit": p.credit, "src": p.src,
        "rights": p.rights, "verified": p.verified,
        "movement": p.movement, "pieces": p.pieces,
    }


@router.get("/puzzles", response_model=list[PuzzleOut])
def list_puzzles(repo: Repo) -> list[dict]:
    """The puzzle catalog. Wall notes are not included; see `/puzzles/{id}`."""
    return [_out(p) for p in repo.list_all()]


@router.get("/puzzles/{puzzle_id}", response_model=PuzzleDetailOut)
def read_puzzle(
    puzzle_id: str,
    repo: Repo,
    progress_pct: Annotated[int, Query(ge=0, le=100)] = 0,
) -> dict:
    """One puzzle plus the wall notes unlocked at `progress_pct`."""
    puzzle = repo.get(puzzle_id)
    if puzzle is None:
        raise HTTPException(404, f"puzzle {puzzle_id!r} not found")
    stories = [
        StoryOut(lede=s.lede, body=s.body, unlock_pct=s.unlock_pct)
        for s in repo.stories(puzzle_id)
        if s.unlocked_at(progress_pct)
    ]
    return {**_out(puzzle), "stories": stories}
