-- Read-only editorial content (ADR-0004). Rebuilt from scratch on every image
-- build by scripts/build_database.py; there are no migrations by design.
PRAGMA foreign_keys = ON;

CREATE TABLE puzzle (
    id         TEXT PRIMARY KEY,
    title     TEXT NOT NULL,
    credit    TEXT NOT NULL,
    src        TEXT NOT NULL,
    rights   TEXT NOT NULL,
    verified INTEGER NOT NULL CHECK (verified IN (0, 1)),
    movement  TEXT NOT NULL,
    pieces      INTEGER NOT NULL CHECK (pieces IN (12, 24, 54, 96))
);

-- unlock_pct = 100 means "revealed on completion only".
CREATE TABLE puzzle_story (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    puzzle_id       TEXT NOT NULL REFERENCES puzzle(id),
    unlock_pct INTEGER NOT NULL CHECK (unlock_pct BETWEEN 0 AND 100),
    lede            TEXT NOT NULL,
    body           TEXT NOT NULL
);

CREATE TABLE tour_link (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    museum  TEXT NOT NULL,
    country TEXT,  -- NULL for links that span many countries
    title   TEXT NOT NULL,
    url     TEXT NOT NULL
);
