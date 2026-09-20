"""Builds the read-only SQLite file from db/schema.sql + db/seed/ (ADR-0004).

Runs at Docker build time, after `pip install .`, because it validates every
seed row through the domain classes: a story pointing at a nonexistent puzzle,
or a malformed URL, fails the build with a clear message instead of shipping a
corrupt database.
"""

import argparse
import sqlite3
import tomllib
from pathlib import Path

from martevi.domain import Puzzle, PuzzleStory, TourLink


def _read_story(path: Path) -> tuple[str, str]:
    lede, _, body = path.read_text(encoding="utf-8").strip().partition("\n\n")
    return lede.strip(), body.strip()


def build(schema: Path, seed: Path, out: Path) -> None:
    puzzles = [
        Puzzle(**row)
        for row in tomllib.loads((seed / "puzzles.toml").read_text(encoding="utf-8"))["puzzle"]
    ]
    ids = {p.id for p in puzzles}
    if len(ids) != len(puzzles):
        raise SystemExit("puzzles.toml has duplicate puzzle ids")

    stories: list[PuzzleStory] = []
    for path in sorted((seed / "stories").glob("*.md")):
        if path.stem not in ids:
            raise SystemExit(f"{path}: no puzzle with id {path.stem!r} in puzzles.toml")
        lede, body = _read_story(path)
        stories.append(PuzzleStory(len(stories) + 1, path.stem, 100, lede, body))

    tours_raw = tomllib.loads((seed / "tours.toml").read_text(encoding="utf-8"))
    tours = [TourLink(i, **row) for i, row in enumerate(tours_raw.get("tour", []), start=1)]

    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    conn = sqlite3.connect(out)
    try:
        conn.executescript(schema.read_text(encoding="utf-8"))
        conn.executemany(
            "INSERT INTO puzzle VALUES (?,?,?,?,?,?,?,?)",
            [
                (p.id, p.title, p.credit, p.src, p.rights, int(p.verified),
                 p.movement, p.pieces)
                for p in puzzles
            ],
        )
        conn.executemany(
            "INSERT INTO puzzle_story (puzzle_id, unlock_pct, lede, body) VALUES (?,?,?,?)",
            [(s.puzzle_id, s.unlock_pct, s.lede, s.body) for s in stories],
        )
        conn.executemany(
            "INSERT INTO tour_link (museum, country, title, url) VALUES (?,?,?,?)",
            [(t.museum, t.country, t.title, t.url) for t in tours],
        )
        conn.commit()
    finally:
        conn.close()
    print(f"Built {out}: {len(puzzles)} puzzles, {len(stories)} stories, {len(tours)} tours")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", type=Path, default=Path("db/schema.sql"))
    parser.add_argument("--seed", type=Path, default=Path("db/seed"))
    parser.add_argument("--out", type=Path, default=Path("/opt/martevi/martevi.db"))
    args = parser.parse_args()
    build(args.schema, args.seed, args.out)
