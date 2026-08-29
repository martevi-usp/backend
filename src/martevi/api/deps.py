from fastapi import Request

from martevi.providers.base import MuseumProvider


def get_registry(request: Request) -> dict[str, MuseumProvider]:
    return request.app.state.registry
