from conftest import FakeProvider

from martevi.providers.fanout import fan_out_search, stream_fan_out_search
from martevi.schema import ArtworkSummary


def _summary(provider_id: str, n: int) -> ArtworkSummary:
    return ArtworkSummary(
        id=f"{provider_id}:{n}",
        provider_id=provider_id,
        title=f"Work {n}",
        date=None,
        thumbnail_url=None,
        height_cm=None,
        width_cm=None,
    )


async def test_all_providers_succeed_merges_results_in_registry_order():
    providers = {
        "a": FakeProvider("a", summaries=[_summary("a", 1)]),
        "b": FakeProvider("b", summaries=[_summary("b", 1), _summary("b", 2)]),
    }

    result = await fan_out_search(providers, "query")

    assert [r.id for r in result.results] == ["a:1", "b:1", "b:2"]
    assert {s.provider_id: s.ok for s in result.provider_status} == {"a": True, "b": True}
    assert {s.provider_id: s.count for s in result.provider_status} == {"a": 1, "b": 2}


async def test_one_provider_raises_others_still_return_with_partial_status():
    providers = {
        "a": FakeProvider("a", summaries=[_summary("a", 1)]),
        "b": FakeProvider("b", error=RuntimeError("boom")),
    }

    result = await fan_out_search(providers, "query")

    assert [r.id for r in result.results] == ["a:1"]
    statuses = {s.provider_id: s for s in result.provider_status}
    assert statuses["a"].ok is True
    assert statuses["b"].ok is False
    assert statuses["b"].error == "boom"


async def test_all_providers_fail_returns_empty_results_all_error_status():
    providers = {
        "a": FakeProvider("a", error=RuntimeError("a failed")),
        "b": FakeProvider("b", error=RuntimeError("b failed")),
    }

    result = await fan_out_search(providers, "query")

    assert result.results == []
    assert all(not s.ok for s in result.provider_status)


async def test_stream_yields_in_completion_order_not_registry_order():
    providers = {
        "slow": FakeProvider("slow", summaries=[_summary("slow", 1)], delay=0.05),
        "fast": FakeProvider("fast", summaries=[_summary("fast", 1)], delay=0),
    }

    order = [status.provider_id async for status, _ in stream_fan_out_search(providers, "query")]

    assert order == ["fast", "slow"]


async def test_stream_yields_results_alongside_each_status():
    providers = {
        "a": FakeProvider("a", summaries=[_summary("a", 1), _summary("a", 2)]),
    }

    outcomes = [
        (status, results) async for status, results in stream_fan_out_search(providers, "q")
    ]

    assert len(outcomes) == 1
    status, results = outcomes[0]
    assert status.provider_id == "a"
    assert status.ok is True
    assert status.count == 2
    assert [r.id for r in results] == ["a:1", "a:2"]


async def test_stream_a_slow_failing_provider_does_not_block_a_fast_one():
    providers = {
        "slow_fail": FakeProvider("slow_fail", error=RuntimeError("boom"), delay=0.05),
        "fast": FakeProvider("fast", summaries=[_summary("fast", 1)]),
    }

    outcomes = [status async for status, _ in stream_fan_out_search(providers, "q")]

    assert [s.provider_id for s in outcomes] == ["fast", "slow_fail"]
    assert outcomes[0].ok is True
    assert outcomes[1].ok is False
    assert outcomes[1].error == "boom"
