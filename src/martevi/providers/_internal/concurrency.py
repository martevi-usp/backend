import asyncio
from collections.abc import Awaitable, Iterable


async def gather_ordered[T](
    coros: Iterable[Awaitable[T]], *, max_concurrency: int = 10
) -> list[T]:
    """Bounded gather preserving order and never dropping results — for concurrent
    work where every coroutine is expected to succeed (unlike gather_optional)."""
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _run(coro: Awaitable[T]) -> T:
        async with semaphore:
            return await coro

    return await asyncio.gather(*(_run(coro) for coro in coros))


async def gather_optional[T](
    coros: Iterable[Awaitable[T | None]], *, max_concurrency: int = 10
) -> list[T]:
    """Bounded gather that drops both None results and exceptions. Used for Met/
    Rijksmuseum's per-id search fan-out and the router's department-filter hydration —
    deliberately distinct from providers/fanout.py, which needs per-provider status,
    not silent dropping."""
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _run(coro: Awaitable[T | None]) -> T | None:
        async with semaphore:
            try:
                return await coro
            except Exception:
                return None

    results = await asyncio.gather(*(_run(coro) for coro in coros))
    return [result for result in results if result is not None]
