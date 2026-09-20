"""The only module that knows the storage engine (ADR-0004)."""

import sqlite3
from pathlib import Path

from martevi.domain import Puzzle, PuzzleStory, TourLink

from .base import PuzzleRepository, TourLinkRepository


def connect_readonly(path: str | Path) -> sqlite3.Connection:
    # FastAPI runs a sync dependency and the sync endpoint that uses it on
    # possibly different worker threads. The connection is opened per request,
    # read-only, and never shared between requests, so lifting sqlite3's
    # same-thread check is safe here.
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


class SqlitePuzzleRepository(PuzzleRepository):
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @staticmethod
    def _puzzle(row: sqlite3.Row) -> Puzzle:
        return Puzzle(**{k: row[k] for k in row.keys()})

    def list_all(self) -> list[Puzzle]:
        rows = self._conn.execute("SELECT * FROM puzzle ORDER BY rowid").fetchall()
        return [self._puzzle(r) for r in rows]

    def get(self, puzzle_id: str) -> Puzzle | None:
        row = self._conn.execute("SELECT * FROM puzzle WHERE id = ?", (puzzle_id,)).fetchone()
        return self._puzzle(row) if row else None

    def stories(self, puzzle_id: str) -> list[PuzzleStory]:
        rows = self._conn.execute(
            "SELECT * FROM puzzle_story WHERE puzzle_id = ? ORDER BY unlock_pct, id",
            (puzzle_id,),
        ).fetchall()
        return [PuzzleStory(**{k: r[k] for k in r.keys()}) for r in rows]


class SqliteTourLinkRepository(TourLinkRepository):
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list_all(self, museum: str | None = None) -> list[TourLink]:
        if museum is None:
            rows = self._conn.execute("SELECT * FROM tour_link ORDER BY museum, id").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM tour_link WHERE museum = ? ORDER BY id", (museum,)
            ).fetchall()
        return [TourLink(**{k: r[k] for k in r.keys()}) for r in rows]
