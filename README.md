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
