from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from martevi.api import artworks_router
from martevi.providers.registry import build_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Some provider APIs (confirmed live: the Met) sit behind a WAF that 403s
    # httpx's default "python-httpx/..." User-Agent — send an identifying one.
    headers = {"User-Agent": "martevi-backend/0.1 (+https://github.com/martevi-usp/martevi)"}
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        app.state.registry = build_registry(client)
        yield


app = FastAPI(lifespan=lifespan)


app.include_router(artworks_router)
