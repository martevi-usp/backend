# martevi — backend

FastAPI service behind martevi's museum-provider adapter. Scaffolded with
[fastapi-gen](https://pypi.org/project/fastapi-gene/); the actual Python
project (`pyproject.toml`, `main.py`) lives in `src/`, one level below
this repo root — that nesting is a fastapi-gen artifact, not a mistake. The
importable `martevi` package itself lives in `src/martevi/`
(src-layout, so it's never importable by accident — only through an actual
install). The Docker/CI setup below accounts for both.

## Local development

```bash
cd src
python3 -m venv ../.venv          # or reuse an existing one
source ../.venv/bin/activate
pip install -e ".[dev]"
fastapi dev main.py
```

Interactive API docs: http://127.0.0.1:8000/docs

> **Heads up:** if you scaffolded this before `pyproject.toml` existed, your
> venv may be missing `uvicorn`/`fastapi-cli` (they come from the
> `fastapi[standard]` extra declared here, not the bare `fastapi` you may
> have installed by hand). Re-run `pip install -e ".[dev]"` if `fastapi dev`
> doesn't start.

## `/artworks` API

Base URL in dev: `http://127.0.0.1:8000` (or `VITE_API_URL` from the root
`.env`). Full interactive docs (OpenAPI/Swagger) are always at `/docs` —
this section is a task-oriented companion for frontend integration.
`title`/`description`/`medium`/`culture` arrive already translated to
pt-BR (see ADR-0001, revised by ADR-0002); everything else (dates,
dimensions, ids, URLs) passes through untouched. Translation runs fully
offline (Argos Translate, in-process, no network call at request time —
ADR-0002) — on a translation failure (e.g. a corrupted/missing model file)
a field silently falls back to its original English text rather than
erroring the whole request, so don't assume every response is 100% pt-BR.

### Search one museum

`GET /artworks?q=<query>&provider_id=<id>&limit=<n>`

`provider_id` is one of `met`, `aic`, `cleveland`, `harvard`,
`rijksmuseum`, `smithsonian`, `vam`. `limit` defaults to 20 (max 100).

`q` can be typed in **either English or Portuguese** — an already-English (or
proper-noun) query is tried as-is first; if that returns nothing, the backend
retries once with the query translated to English before giving up. This
means a genuinely-empty result and "wrong language" both cost one extra
round-trip on the backend, but the frontend never needs to translate the
query itself or know which language the user typed.

```ts
const res = await fetch(
  `${API_URL}/artworks?q=sunflowers&provider_id=met&limit=10`
);
const { results, provider_status } = await res.json();
```

```json
{
  "results": [
    {
      "id": "met:436524",
      "provider_id": "met",
      "title": "Girassóis",
      "date": "1887",
      "thumbnail_url": "https://images.metmuseum.org/.../DP-41223-001.jpg",
      "height_cm": 43.2,
      "width_cm": 61.0
    }
  ],
  "provider_status": [
    { "provider_id": "met", "ok": true, "count": 1, "error": null }
  ]
}
```

Results are `ArtworkSummary` — enough for a search grid/card, not the full
detail view (no `description`/`medium`/`culture`/etc.).

### Search across every museum ("Museu Martevi")

Omit `provider_id` and the same endpoint fans out to all 7 providers at
once, tolerating any one of them being down or throttled:

```ts
const res = await fetch(`${API_URL}/artworks?q=sunflowers`);
const { results, provider_status } = await res.json();
```

`provider_status` has one entry per registered provider — check `ok`
before treating a provider's absence from `results` as "no matches"
rather than "it failed":

```json
{
  "results": [ /* merged summaries from every provider that succeeded */ ],
  "provider_status": [
    { "provider_id": "met", "ok": true, "count": 3, "error": null },
    { "provider_id": "smithsonian", "ok": false, "count": 0, "error": "..." }
  ]
}
```

### Filter by department (one museum at a time)

`department` is only valid together with `provider_id` — a department only
means something within one museum, so combining it with the fan-out view
(no `provider_id`) is a `400`:

```ts
const dept = encodeURIComponent("European Paintings");
const res = await fetch(
  `${API_URL}/artworks?q=painting&provider_id=met&department=${dept}`
);
```

### Get one artwork's full detail

`GET /artworks/{id}` — `id` is the composite id from a search result
(`"{provider_id}:{external_id}"`, e.g. `"met:436524"`). Some providers'
own external ids contain colons too (e.g.
`"smithsonian:edanmdm:saam_1985.66.403_415"`) — only the *first* colon
separates the provider, so pass the id straight through rather than
re-parsing it yourself:

```ts
const res = await fetch(`${API_URL}/artworks/${encodeURIComponent(artworkId)}`);
if (res.status === 404) { /* unknown provider, or not found */ }
const artwork = await res.json(); // full Artwork — adds description,
                                   // medium, culture, department,
                                   // image_url, image_zoom_url, source_url
```

### Error responses

| Status | When |
| --- | --- |
| `400` | `department` given without `provider_id`, or a malformed `/artworks/{id}` (no `:`) |
| `404` | Unknown `provider_id`, or the artwork wasn't found by that provider |

### Fields that are legitimately `null`

Every field beyond `id`/`provider_id`/`title` is `Optional` and genuinely
absent for some providers/artworks — never fabricated, never `0`/`""` as a
stand-in. Render "não informado" (or similar) rather than assume a missing
`height_cm`/`description`/`culture`/etc. is a bug. See
`docs/adr/0001-provider-integration-and-translation.md` for the full
per-provider field-mapping rationale.

## Tests & lint

```bash
pytest
ruff check .
mypy . --ignore-missing-imports
```

## Docker

Two build targets — `dev` (editable install, reload, meant to run against a
bind-mounted source tree) and `production` (locked install, no reload, runs
as a non-root user):

```bash
docker build --target dev        -t martevi-backend:dev .
docker build --target production -t martevi-backend:prod .
docker run --rm -p 8000:8000 martevi-backend:dev
```

In normal day-to-day work you won't run this directly — use
`docker compose up` from the martevi root, which builds this with the `dev`
target and bind-mounts `src/` for live reload.

## CI

`.github/workflows/ci.yml` runs ruff, mypy (non-blocking for now), pytest,
and a production Docker build on every push/PR to `main`.
