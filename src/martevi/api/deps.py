import os
import sqlite3
from collections.abc import Iterator

from fastapi import HTTPException, Request

from martevi.providers.base import MuseumProvider
from martevi.repositories import (
    PuzzleRepository,
    SqlitePuzzleRepository,
    SqliteTourLinkRepository,
    TourLinkRepository,
)
from martevi.repositories.sqlite import connect_readonly


def get_registry(request: Request) -> dict[str, MuseumProvider]:
    return request.app.state.registry


DEFAULT_DB_PATH = "/opt/martevi/martevi.db"


def _connect() -> sqlite3.Connection:
    try:
        return connect_readonly(os.environ.get("MARTEVI_DB_PATH", DEFAULT_DB_PATH))
    except sqlite3.OperationalError as exc:
        raise HTTPException(503, "curated content database is unavailable") from exc


def get_puzzle_repository() -> Iterator[PuzzleRepository]:
    conn = _connect()
    try:
        yield SqlitePuzzleRepository(conn)
    finally:
        conn.close()


def get_tour_link_repository() -> Iterator[TourLinkRepository]:
    conn = _connect()
    try:
        yield SqliteTourLinkRepository(conn)
    finally:
        conn.close()
