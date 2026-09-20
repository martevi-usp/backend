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

COPY src/ ./

# Argos Translate (ADR-0002, ADR-0005): a fixed, non-home path so the same
# installed models are readable regardless of which user ends up running the
# server (dev runs as root; production switches to appuser below) — installed
# once here, in the shared base layer. This RUN needs network access (package
# index, model files, MiniSBD models); the point of doing it at build time is
# that the *running container* never does.
#
# argostranslate is installed --no-deps: its declared deps pull in torch (and
# on Linux the whole CUDA stack, 4+ GB) via stanza, which the default MiniSBD
# sentence splitter never uses. The real runtime deps come from pyproject.toml;
# ARGOS_CHUNK_TYPE=MINISBD is required: the published en/pt model packages
# embed a Stanza tokenizer, which Argos would otherwise select. A stub
# `stanza` satisfies argostranslate's unguarded `import stanza`.
# Review this block on every argostranslate bump.
ENV XDG_DATA_HOME=/opt/argos-translate/data \
    ARGOS_PACKAGES_DIR=/opt/argos-translate/packages \
    ARGOS_DEVICE_TYPE=cpu \
    ARGOS_CHUNK_TYPE=MINISBD
RUN pip install ctranslate2 sentencepiece sacremoses minisbd packaging && \
    pip install --no-deps argostranslate==1.11.0 && \
    mkdir -p "$(python -c 'import site; print(site.getsitepackages()[0])')/stanza" && \
    echo "# stub: see ADR-0005" > "$(python -c 'import site; print(site.getsitepackages()[0])')/stanza/__init__.py" && \
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
