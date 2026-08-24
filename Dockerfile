# syntax=docker/dockerfile:1

# martevi backend — FastAPI service.
# Build contexts: this file is meant to be built with `context: ./backend`
# (see ../docker-compose.yml). The actual Python project lives one level
# down, in src/ (that's where fastapi-gen scaffolded it — pyproject.toml,
# main.py, and the importable `martevi` package all sit there).
#
# Two targets:
#   dev        - editable install, `fastapi dev` with reload, meant to run
#                against a bind-mounted source tree (see docker-compose.yml).
#   production - locked install, `fastapi run` (uvicorn, no reload).
#
# Usage:
#   docker build --target dev        -t martevi-backend:dev .
#   docker build --target production -t martevi-backend:prod .

FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps for building wheels (psycopg2 etc. once a DB driver is added).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY src/ ./

FROM base AS dev

RUN pip install -e ".[dev]"

EXPOSE 8000
CMD ["fastapi", "dev", "main.py", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS production

RUN pip install .

RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000
CMD ["fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]
