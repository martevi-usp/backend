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

# Argos Translate (ADR-0002): a fixed, non-home path so the same installed
# models are readable regardless of which user ends up running the server
# (dev runs as root; production switches to appuser below) — installed once
# here, in the shared base layer, so dev/production don't each download
# their own ~80MB-per-language-pair copy. This RUN needs network access (to
# fetch the package index and model files); the point of doing it at build
# time is that the *running container* never does.
ENV ARGOS_PACKAGES_DIR=/opt/argos-translate/packages \
    ARGOS_DEVICE_TYPE=cpu
RUN pip install argostranslate>=1.11 && \
    python scripts/install_translation_models.py && \
    chmod -R a+rX /opt/argos-translate

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
