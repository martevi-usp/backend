# ADR-0004: Read-Only SQLite Persistence, No ORM

**Status:** Proposed
**Date:** 2026-09-20
**Deciders:** martevi backend owner(s)

## Context

The course brief requires persistence in the "web system" track, and the backend has none: `sqlalchemy` and `alembic` are declared in `pyproject.toml` but no database, schema, or migration exists. ADR-0001 explicitly left curated data out of scope ("not provider-API concerns at all"), so three kinds of editorial content have no home:

- `puzzle` — which artwork is offered as a jigsaw, at what grid size. Today this lives in the frontend (`src/components/artworks.ts`); see frontend ADR-0005.
- `puzzle_story` — the wall-note text unlocked by the puzzle.
- `tour_link` — curated virtual-tour URLs.

Artwork metadata itself (titles, images, dimensions) stays provider-fetched and translated per ADR-0001/0002; this ADR adds no cache or override layer over it.

## Decision

**Persistence is a read-only SQLite file built into the Docker image.**

- Generated at image build time by `scripts/build_database.py` from `db/schema.sql` plus `db/seed/` (TOML for curation, Markdown for long text). Stored at `/opt/martevi/martevi.db` — not under `/app`, because the dev compose target bind-mounts `./backend/src` over `/app` and would shadow it.
- Opened with `sqlite3.connect("file:...?mode=ro", uri=True)`. The application reads and never writes; curation changes ship as a redeploy.
- The seed script runs **after** `pip install .` because it imports the domain classes to validate the seed; a story pointing at a nonexistent puzzle fails the build with a clear message. A Python script rather than `seed.sql` because the editorial text is Portuguese prose full of apostrophes, and one escaping error would break the whole build.
- The Portuguese editorial text is stored as written and **does not** pass through `TranslatingProvider`, which exists to translate provider English. An English version, if wanted, is a second column, not a translation call.

**Naming.** Code, schema columns and API fields are in English, consistent with the rest of the backend; only the editorial content (titles, wall notes, tour labels) is Portuguese.

**No ORM.** `sqlalchemy` and `alembic` are removed. `sqlite3` is stdlib.

- Domain: `CuratedItem` (abstract) with `Puzzle`, `PuzzleStory`, `TourLink`. Private attributes behind read-only properties, validation in `__init__` so an invalid object cannot exist; business rules on the classes, not in endpoints.
- Repository: `PuzzleRepository` / `TourLinkRepository` ABCs with `Sqlite…Repository` as the only implementations; SQL lives in one module. Endpoints depend on the abstraction via FastAPI `Depends`, mirroring the provider registry.
- Pydantic models remain the HTTP boundary and stay distinct from the domain classes.

## Options Considered

### Hosted Postgres (Render) / Neon / Cloudflare D1

Render's free Postgres expires 30 days after creation regardless of traffic — provisioned now, it would be gone before the 2026-12-01 delivery. Neon has no expiry and is the right choice if the app ever needs runtime writes, but for read-only data it adds a second cold start and an external credential. D1 means raw SQL over an HTTP round trip plus a Node toolchain in the backend repo. All rejected because the data is small, versioned in git, and never written at runtime.

### SQLAlchemy + Alembic (already installed)

Incremental migrations exist to evolve a live database that cannot be recreated. This one is rebuilt on every build; a revision chain would be ceremony with no function. The ORM would also hide the encapsulation and polymorphism the course criteria ask us to demonstrate in our own code.

### Admin dashboard with authentication

Considered and cut. Auth is the largest scope addition available, and it would be the only reason to want runtime writes. Cutting it is what makes read-only coherent rather than a compromise.

## Consequences

- Content changes require a redeploy; there is no runtime editing.
- Project documentation must state the read-only decision explicitly rather than let an evaluator infer persistence is absent.
- Speculative abstraction, stated honestly: with one concrete implementation the repository ABC is not load-bearing by product standards. It is justified by the course criterion (inheritance/polymorphism) and by letting tests substitute an in-memory double.
- We maintain the SQL and row-to-object mapping by hand.
- The seed step costs Docker layer cache on every code edit — the deliberate price of build-time validation.
- **Spoiler limitation.** The API can withhold story text until told the puzzle is solved, but with no auth the client reports its own progress, so this is a courtesy, not a guarantee. Completion-only unlock is the initial scope; `unlock_pct` (100 = on completion) is kept in the schema so progressive unlock stays possible later.
- `*.db` is gitignored; `db/schema.sql` and `db/seed/` are versioned. `.env.example`'s `DATABASE_URL` placeholder is removed rather than wired.
