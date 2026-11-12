import httpx

from martevi.providers.adapters.met import MetProvider

_SEARCH_URL = "https://collectionapi.metmuseum.org/public/collection/v1.1/search"
_OBJECT_URL = "https://collectionapi.metmuseum.org/public/collection/v1/objects/436535"

_OBJECT = {
    "objectID": 436535,
    "title": "Wheat Field with Cypresses",
    "objectDate": "1889",
    "medium": "Oil on canvas",
    "culture": "",
    "department": "European Paintings",
    "primaryImage": "https://example.org/full.jpg",
    "objectURL": "https://www.metmuseum.org/art/collection/search/436535",
    "measurements": [
        {"elementName": "Overall", "elementMeasurements": {"Height": 73.2, "Width": 93.4}},
        {"elementName": "Glazing", "elementMeasurements": {"Height": 75.2, "Width": 94.9}},
    ],
}


async def test_get_item_normalizes_overall_measurements_and_blank_culture(respx_mock, async_client):
    respx_mock.get(_OBJECT_URL).mock(return_value=httpx.Response(200, json=_OBJECT))
    provider = MetProvider(async_client)

    artwork = await provider.get_item("436535")

    assert artwork is not None
    assert artwork.id == "met:436535"
    assert artwork.title == "Wheat Field with Cypresses"
    assert artwork.height_cm == 73.2
    assert artwork.width_cm == 93.4
    assert artwork.culture is None  # "" must become None, never invented
    assert artwork.description is None  # Met has no description field at all
    assert artwork.image_zoom_url is None  # Met has no IIIF


async def test_get_item_returns_none_on_404(respx_mock, async_client):
    respx_mock.get(_OBJECT_URL).mock(return_value=httpx.Response(404))
    provider = MetProvider(async_client)

    assert await provider.get_item("436535") is None


async def test_search_fans_out_to_get_item_per_id(respx_mock, async_client):
    respx_mock.get(_SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"total": 1, "objectIDs": [436535]})
    )
    respx_mock.get(_OBJECT_URL).mock(return_value=httpx.Response(200, json=_OBJECT))
    provider = MetProvider(async_client)

    results = await provider.search("wheat", limit=20)

    assert len(results) == 1
    assert results[0].id == "met:436535"


async def test_browse_uses_highlight_and_has_images_filters(respx_mock, async_client):
    route = respx_mock.get(_SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"total": 1, "objectIDs": [436535]})
    )
    respx_mock.get(_OBJECT_URL).mock(return_value=httpx.Response(200, json=_OBJECT))
    provider = MetProvider(async_client)

    results = await provider.browse(limit=20, offset=0)

    assert len(results) == 1
    assert route.calls.last.request.url.params["isHighlight"] == "true"
    assert route.calls.last.request.url.params["hasImages"] == "true"


async def test_browse_paginates_server_side_with_limit_and_offset(respx_mock, async_client):
    route = respx_mock.get(_SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"total": 1982, "objectIDs": [100005, 100006]})
    )
    fetched_ids: list[str] = []

    def _respond(request: httpx.Request) -> httpx.Response:
        external_id = request.url.path.rsplit("/", 1)[-1]
        fetched_ids.append(external_id)
        return httpx.Response(200, json={**_OBJECT, "objectID": int(external_id)})

    respx_mock.get(url__regex=r".*/objects/\d+$").mock(side_effect=_respond)
    provider = MetProvider(async_client)

    await provider.browse(limit=2, offset=5)

    params = route.calls.last.request.url.params
    assert params["limit"] == "2"
    assert params["offset"] == "5"
    assert sorted(fetched_ids) == ["100005", "100006"]
