import asyncio

from martevi.providers.base import MuseumProvider
from martevi.schema import FanOutSearchResult, ProviderSearchStatus


async def fan_out_search(
    providers: dict[str, MuseumProvider], query: str, limit: int = 20
) -> FanOutSearchResult:
    """Searches every provider concurrently. A provider that raises doesn't take the
    whole request down — its failure is reported in provider_status instead."""
    provider_ids = list(providers)
    outcomes = await asyncio.gather(
        *(providers[pid].search(query, limit) for pid in provider_ids),
        return_exceptions=True,
    )

    results = []
    statuses = []
    for provider_id, outcome in zip(provider_ids, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            status = ProviderSearchStatus(provider_id=provider_id, ok=False, error=str(outcome))
        else:
            results.extend(outcome)
            status = ProviderSearchStatus(provider_id=provider_id, ok=True, count=len(outcome))
        statuses.append(status)

    return FanOutSearchResult(results=results, provider_status=statuses)
