import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from martevi.api import puzzles_router, tours_router
from martevi.api.deps import get_puzzle_repository
from martevi.domain import CuratedItem, Puzzle, PuzzleStory, TourLink
from martevi.repositories import PuzzleRepository
from martevi.repositories.sqlite import SqlitePuzzleRepository, connect_readonly
from scripts.build_database import build

DB_DIR = Path(__file__).resolve().parents[2] / "db"


def make_puzzle(**over) -> Puzzle:
    args = dict(
        id="p1", title="T", credit="C", src="https://x/y.jpg",
        rights="PD", verified=True, movement="M", pieces=24,
    )
    return Puzzle(**{**args, **over})


# ── domain ────────────────────────────────────────────────────────────


def test_curated_item_is_abstract():
    with pytest.raises(TypeError):
        CuratedItem("x")  # type: ignore[abstract]


@pytest.mark.parametrize(
    "over", [{"pieces": 13}, {"title": " "}, {"src": "ftp://x"}, {"id": ""}]
)
def test_invalid_puzzle_cannot_exist(over):
    with pytest.raises(ValueError):
        make_puzzle(**over)


def test_puzzle_is_read_only():
    with pytest.raises(AttributeError):
        make_puzzle().title = "other"  # type: ignore[misc]


def test_progress_pct():
    p = make_puzzle(pieces=24)
    assert p.progress_pct(0) == 0
    assert p.progress_pct(12) == 50
    assert p.progress_pct(24) == 100
    with pytest.raises(ValueError):
        p.progress_pct(25)


def test_story_unlock_rule():
    s = PuzzleStory(1, "p1", 100, "lede", "body")
    assert not s.unlocked_at(99)
    assert s.unlocked_at(100)


def test_tour_link_requires_http_url():
    with pytest.raises(ValueError):
        TourLink(1, "Prado", "Visita", "prado.es")


# ── build script + real seed ─────────────────────────────────────────


@pytest.fixture(scope="module")
def db_path(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("db") / "martevi.db"
    build(DB_DIR / "schema.sql", DB_DIR / "seed", out)
    return out


def test_built_database_is_read_only(db_path):
    conn = connect_readonly(db_path)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM puzzle")


def test_repository_maps_rows_to_domain_objects(db_path):
    repo = SqlitePuzzleRepository(connect_readonly(db_path))
    puzzles = repo.list_all()
    assert len(puzzles) > 0 and all(isinstance(p, Puzzle) for p in puzzles)
    assert repo.get("vermeer-leiteira").title == "A leiteira"
    assert repo.get("nope") is None
    assert repo.stories("vermeer-leiteira")[0].unlock_pct == 100


def test_seed_with_orphan_story_fails_the_build(tmp_path):
    seed = tmp_path / "seed"
    (seed / "stories").mkdir(parents=True)
    (seed / "puzzles.toml").write_text(
        '[[puzzle]]\nid="a"\ntitle="T"\ncredit="C"\nsrc="https://x"\nrights="d"\n'
        'verified=true\nmovement="m"\npieces=24\n'
    )
    (seed / "tours.toml").write_text("")
    (seed / "stories" / "missing.md").write_text("lede\n\ncorpo\n")
    with pytest.raises(SystemExit, match="missing"):
        build(DB_DIR / "schema.sql", seed, tmp_path / "out.db")


# ── HTTP, through the abstraction (also proves a test double substitutes) ──


class InMemoryPuzzles(PuzzleRepository):
    def __init__(self):
        self._p = make_puzzle()
        self._s = [PuzzleStory(1, "p1", 50, "meio", "c"), PuzzleStory(2, "p1", 100, "fim", "c")]

    def list_all(self):
        return [self._p]

    def get(self, puzzle_id):
        return self._p if puzzle_id == "p1" else None

    def stories(self, puzzle_id):
        return self._s


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(puzzles_router)
    app.include_router(tours_router)
    app.dependency_overrides[get_puzzle_repository] = InMemoryPuzzles
    return TestClient(app)


def test_list_puzzles_has_no_stories(client):
    body = client.get("/puzzles").json()
    assert body[0]["id"] == "p1" and "stories" not in body[0]


def test_stories_are_filtered_by_progress(client):
    def lides(pct):
        r = client.get("/puzzles/p1", params={"progress_pct": pct}).json()
        return [h["lede"] for h in r["stories"]]

    assert lides(0) == []
    assert lides(50) == ["meio"]
    assert lides(100) == ["meio", "fim"]


def test_unknown_puzzle_is_404(client):
    assert client.get("/puzzles/nope").status_code == 404


def test_missing_database_is_503(monkeypatch, tmp_path):
    monkeypatch.setenv("MARTEVI_DB_PATH", str(tmp_path / "absent.db"))
    app = FastAPI()
    app.include_router(tours_router)
    assert TestClient(app).get("/tours").status_code == 503


def test_seeded_tour_links_are_served(db_path):
    from martevi.repositories.sqlite import SqliteTourLinkRepository

    repo = SqliteTourLinkRepository(connect_readonly(db_path))
    tours = repo.list_all()
    assert len(tours) == 36
    assert all(t.url.startswith(("http://", "https://")) for t in tours)
    assert [t.title for t in repo.list_all("Museu Britânico")] == ["Street View"]
    # Every link names a country except the multi-country Google hub.
    assert [t.museum for t in tours if t.country is None] == ["Google Arts & Culture"]
    assert {t.country for t in tours if t.museum == "Museu Britânico"} == {"United Kingdom"}


def test_connection_can_be_used_from_another_thread(db_path):
    # FastAPI opens the connection in a dependency and uses it in the endpoint,
    # which may run on a different worker thread.
    from concurrent.futures import ThreadPoolExecutor

    conn = connect_readonly(db_path)
    with ThreadPoolExecutor(max_workers=1) as pool:
        query = "SELECT COUNT(*) FROM puzzle"
        count = pool.submit(lambda: conn.execute(query).fetchone()[0]).result()
    assert count > 0
