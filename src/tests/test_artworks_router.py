import json

from conftest import FakeProvider

from martevi.schema import Artwork, ArtworkSummary


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    """Splits a raw SSE response body into (event, parsed-json-data) pairs."""
    events = []
    for frame in body.strip().split("\n\n"):
        if not frame:
            continue
        lines = frame.splitlines()
        event = next(line.removeprefix("event: ") for line in lines if line.startswith("event: "))
        data = next(line.removeprefix("data: ") for line in lines if line.startswith("data: "))
        events.append((event, json.loads(data)))
    return events


def _artwork(provider_id: str, external_id: str, department: str | None = None) -> Artwork:
    return Artwork(
        id=f"{provider_id}:{external_id}",
        provider_id=provider_id,
        title=f"Work {external_id}",
        date=None,
        thumbnail_url=None,
        height_cm=None,
        width_cm=None,
        description=None,
        medium=None,
        culture=None,
        department=department,
        image_url=None,
        image_zoom_url=None,
        source_url=None,
    )


def _summary_of(artwork: Artwork) -> ArtworkSummary:
    return ArtworkSummary(
        id=artwork.id,
        provider_id=artwork.provider_id,
        title=artwork.title,
        date=artwork.date,
        thumbnail_url=artwork.thumbnail_url,
        height_cm=artwork.height_cm,
        width_cm=artwork.width_cm,
    )


def test_search_single_provider(make_test_client):
    artwork = _artwork("met", "1")
    registry = {"met": FakeProvider("met", summaries=[_summary_of(artwork)])}
    client = make_test_client(registry)

    response = client.get("/artworks", params={"q": "test", "provider_id": "met"})

    assert response.status_code == 200
    body = response.json()
    assert [r["id"] for r in body["results"]] == ["met:1"]
    expected_status = {"provider_id": "met", "ok": True, "count": 1, "error": None}
    assert body["provider_status"] == [expected_status]


def test_search_fan_out_all_providers(make_test_client):
    met_artwork = _artwork("met", "1")
    aic_artwork = _artwork("aic", "2")
    registry = {
        "met": FakeProvider("met", summaries=[_summary_of(met_artwork)]),
        "aic": FakeProvider("aic", summaries=[_summary_of(aic_artwork)]),
    }
    client = make_test_client(registry)

    response = client.get("/artworks", params={"q": "test"})

    assert response.status_code == 200
    body = response.json()
    assert {r["id"] for r in body["results"]} == {"met:1", "aic:2"}
    assert len(body["provider_status"]) == 2


def test_search_unknown_provider_id_404(make_test_client):
    client = make_test_client({})

    response = client.get("/artworks", params={"q": "test", "provider_id": "nope"})

    assert response.status_code == 404


def test_get_by_id_splits_on_first_colon(make_test_client):
    artwork = _artwork("smithsonian", "edanmdm:saam_1985.66.403_415")
    external_id = artwork.id.split(":", 1)[1]
    registry = {"smithsonian": FakeProvider("smithsonian", items={external_id: artwork})}
    client = make_test_client(registry)

    response = client.get(f"/artworks/{artwork.id}")

    assert response.status_code == 200
    assert response.json()["id"] == artwork.id


def test_get_by_id_unknown_provider_404(make_test_client):
    client = make_test_client({})

    response = client.get("/artworks/nope:1")

    assert response.status_code == 404


def test_get_by_id_not_found_404(make_test_client):
    registry = {"met": FakeProvider("met", items={})}
    client = make_test_client(registry)

    response = client.get("/artworks/met:999")

    assert response.status_code == 404


def test_department_filter_requires_provider_id_400(make_test_client):
    client = make_test_client({})

    response = client.get("/artworks", params={"q": "test", "department": "Paintings"})

    assert response.status_code == 400


def test_department_filter_narrows_results(make_test_client):
    matching = _artwork("met", "1", department="Paintings")
    other = _artwork("met", "2", department="Sculpture")
    registry = {
        "met": FakeProvider(
            "met",
            summaries=[_summary_of(matching), _summary_of(other)],
            items={"1": matching, "2": other},
        )
    }
    client = make_test_client(registry)

    response = client.get(
        "/artworks", params={"q": "test", "provider_id": "met", "department": "paintings"}
    )

    assert response.status_code == 200
    body = response.json()
    assert [r["id"] for r in body["results"]] == ["met:1"]


def test_browse_single_provider_when_q_omitted(make_test_client):
    artworks = [_artwork("met", str(i)) for i in range(5)]
    registry = {"met": FakeProvider("met", summaries=[_summary_of(a) for a in artworks])}
    client = make_test_client(registry)

    response = client.get("/artworks", params={"provider_id": "met", "limit": 3})

    assert response.status_code == 200
    body = response.json()
    assert [r["id"] for r in body["results"]] == ["met:0", "met:1", "met:2"]
    assert body["provider_status"] == [
        {"provider_id": "met", "ok": True, "count": 3, "error": None}
    ]


def test_browse_honors_offset(make_test_client):
    artworks = [_artwork("met", str(i)) for i in range(5)]
    registry = {"met": FakeProvider("met", summaries=[_summary_of(a) for a in artworks])}
    client = make_test_client(registry)

    response = client.get(
        "/artworks", params={"provider_id": "met", "limit": 2, "offset": 3}
    )

    assert response.status_code == 200
    assert [r["id"] for r in response.json()["results"]] == ["met:3", "met:4"]


def test_browse_without_provider_id_400(make_test_client):
    client = make_test_client({})

    response = client.get("/artworks")

    assert response.status_code == 400


def test_browse_with_department_400(make_test_client):
    registry = {"met": FakeProvider("met", summaries=[])}
    client = make_test_client(registry)

    response = client.get(
        "/artworks", params={"provider_id": "met", "department": "Paintings"}
    )

    assert response.status_code == 400


def test_stream_emits_one_provider_event_per_provider_then_done(make_test_client):
    met_artwork = _artwork("met", "1")
    aic_artwork = _artwork("aic", "2")
    registry = {
        "met": FakeProvider("met", summaries=[_summary_of(met_artwork)]),
        "aic": FakeProvider("aic", summaries=[_summary_of(aic_artwork)]),
    }
    client = make_test_client(registry)

    response = client.get("/artworks/stream", params={"q": "test"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(response.text)

    assert [event for event, _ in events] == ["provider", "provider", "done"]
    provider_ids = {data["provider_id"] for event, data in events if event == "provider"}
    assert provider_ids == {"met", "aic"}
    for event, data in events:
        if event == "provider":
            assert data["ok"] is True
            assert data["count"] == 1
            assert len(data["results"]) == 1


def test_stream_reports_a_failing_provider_without_dropping_others(make_test_client):
    registry = {
        "met": FakeProvider("met", summaries=[_summary_of(_artwork("met", "1"))]),
        "aic": FakeProvider("aic", error=RuntimeError("boom")),
    }
    client = make_test_client(registry)

    response = client.get("/artworks/stream", params={"q": "test"})

    events = _parse_sse(response.text)
    provider_events = {data["provider_id"]: data for event, data in events if event == "provider"}

    assert provider_events["met"]["ok"] is True
    assert provider_events["aic"]["ok"] is False
    assert provider_events["aic"]["error"] == "boom"
    assert [event for event, _ in events][-1] == "done"


def test_stream_requires_q(make_test_client):
    client = make_test_client({})

    response = client.get("/artworks/stream")

    assert response.status_code == 422
