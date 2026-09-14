import asyncio
from collections.abc import AsyncIterator, Callable

from martevi.providers.base import MuseumProvider
from martevi.schema import ArtworkSummary, FanOutSearchResult, ProviderSearchStatus


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


async def stream_fan_out_search(
    providers: dict[str, MuseumProvider], query: str, limit: int = 20
) -> AsyncIterator[tuple[ProviderSearchStatus, list[ArtworkSummary]]]:
    """Like fan_out_search, but yields each provider's outcome as soon as it
    finishes rather than waiting for all of them — so a slow provider (or one
    that errors) never delays a faster provider's results from reaching the
    client. Yield order is completion order, not registry order.

    Uses an explicit queue of (provider_id, task) fed by per-task done
    callbacks rather than asyncio.as_completed: as_completed wraps each
    awaitable in a new future internally and yields those wrappers, not the
    original task objects, so a dict keyed by the original tasks can't be
    used to recover which provider finished.
    """
    queue: asyncio.Queue[tuple[str, asyncio.Task[list[ArtworkSummary]]]] = asyncio.Queue()

    def _on_done(provider_id: str, task: asyncio.Task[list[ArtworkSummary]]) -> None:
        queue.put_nowait((provider_id, task))

    def _make_callback(
        provider_id: str,
    ) -> Callable[[asyncio.Task[list[ArtworkSummary]]], None]:
        return lambda task: _on_done(provider_id, task)

    tasks = []
    for provider_id, provider in providers.items():
        task = asyncio.ensure_future(provider.search(query, limit))
        task.add_done_callback(_make_callback(provider_id))
        tasks.append(task)

    for _ in tasks:
        provider_id, task = await queue.get()
        try:
            results = task.result()
        except Exception as exc:
            yield ProviderSearchStatus(provider_id=provider_id, ok=False, error=str(exc)), []
        else:
            status = ProviderSearchStatus(provider_id=provider_id, ok=True, count=len(results))
            yield status, results
