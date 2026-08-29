from pydantic import BaseModel

from martevi.schema.artwork import ArtworkSummary


class ProviderSearchStatus(BaseModel):
    provider_id: str
    ok: bool
    count: int = 0
    error: str | None = None


class FanOutSearchResult(BaseModel):
    results: list[ArtworkSummary]
    provider_status: list[ProviderSearchStatus]
