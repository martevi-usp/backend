import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from martevi.api import (
    artworks_router,
    health_router,
    images_router,
    puzzles_router,
    tours_router,
)
from martevi.providers.registry import build_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Some provider APIs (confirmed live: the Met) sit behind a WAF that 403s
    # httpx's default "python-httpx/..." User-Agent — send an identifying one.
    headers = {"User-Agent": "martevi-backend/0.1 (+https://github.com/martevi-usp/martevi)"}
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        app.state.http_client = client
        app.state.registry = build_registry(client)
        yield


app = FastAPI(lifespan=lifespan)

# The frontend calls this API directly from the browser, so it needs CORS —
# see CORS_ORIGINS in .env.example. GET-only since that's the whole surface.
# CORS_ORIGIN_REGEX additionally admits origins by pattern (e.g. per-branch
# preview subdomains); Starlette full-matches it, and unset means exact-only.
_cors_origins = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=os.environ.get("CORS_ORIGIN_REGEX") or None,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(artworks_router)
app.include_router(images_router)
app.include_router(puzzles_router)
app.include_router(tours_router)
