import asyncio

from martevi.providers._internal.concurrency import gather_ordered


async def test_gather_ordered_preserves_input_order():
    async def _value(n: int) -> int:
        await asyncio.sleep(0.01 * (5 - n))  # later items finish first
        return n

    results = await gather_ordered(_value(n) for n in range(5))

    assert results == [0, 1, 2, 3, 4]


async def test_gather_ordered_runs_concurrently():
    concurrent = 0
    max_concurrent = 0

    async def _track() -> None:
        nonlocal concurrent, max_concurrent
        concurrent += 1
        max_concurrent = max(max_concurrent, concurrent)
        await asyncio.sleep(0.01)
        concurrent -= 1

    await gather_ordered((_track() for _ in range(5)), max_concurrency=5)

    assert max_concurrent > 1


async def test_gather_ordered_respects_max_concurrency():
    concurrent = 0
    max_concurrent = 0

    async def _track() -> None:
        nonlocal concurrent, max_concurrent
        concurrent += 1
        max_concurrent = max(max_concurrent, concurrent)
        await asyncio.sleep(0.01)
        concurrent -= 1

    await gather_ordered((_track() for _ in range(10)), max_concurrency=2)

    assert max_concurrent <= 2
