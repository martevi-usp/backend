import httpx

from martevi.providers.adapters.aic import AicProvider

_SEARCH_URL = "https://api.artic.edu/api/v1/artworks/search"
_ITEM_URL = "https://api.artic.edu/api/v1/artworks/129884"
_IIIF_URL = "https://www.artic.edu/iiif/2"

_ITEM = {
    "data": {
        "id": 129884,
        "title": "Starry Night and the Astronauts",
        "date_display": "1972",
        "medium_display": "Acrylic on canvas",
        "department_title": "Contemporary Art",
        "short_description": "A short curatorial summary.",
        "description": "<p>Full HTML description.</p>",
        "image_id": "e966799b-97ee-1cc6-bd2f-a94b4b8bb8f9",
        "dimensions_detail": [{"height": 152, "width": 134, "depth": None, "diameter": None}],
    },
    "config": {"iiif_url": _IIIF_URL},
}


async def test_get_item_normalizes_cm_dimensions_and_constructs_iiif_and_source_url(
    respx_mock, async_client
):
    respx_mock.get(_ITEM_URL).mock(return_value=httpx.Response(200, json=_ITEM))
    provider = AicProvider(async_client)

    artwork = await provider.get_item("129884")

    assert artwork is not None
    assert artwork.height_cm == 152
    assert artwork.width_cm == 134
    assert artwork.culture is None  # AIC has no culture-equivalent field
    assert artwork.description == "A short curatorial summary."
    image_id = "e966799b-97ee-1cc6-bd2f-a94b4b8bb8f9"
    assert artwork.image_url == f"{_IIIF_URL}/{image_id}/full/full/0/default.jpg"
    assert artwork.image_zoom_url == f"{_IIIF_URL}/{image_id}"
    assert artwork.source_url == "https://www.artic.edu/artworks/129884"


async def test_get_item_missing_image_id_yields_none_urls(respx_mock, async_client):
    item = {"data": {**_ITEM["data"], "image_id": None}, "config": {"iiif_url": _IIIF_URL}}
    respx_mock.get(_ITEM_URL).mock(return_value=httpx.Response(200, json=item))
    provider = AicProvider(async_client)

    artwork = await provider.get_item("129884")

    assert artwork is not None
    assert artwork.image_url is None
    assert artwork.image_zoom_url is None
    assert artwork.thumbnail_url is None


async def test_search_returns_summaries_without_follow_up_calls(respx_mock, async_client):
    payload = {
        "data": [
            {
                "id": 129884,
                "title": "Starry Night and the Astronauts",
                "date_display": "1972",
                "image_id": "e966799b-97ee-1cc6-bd2f-a94b4b8bb8f9",
                "dimensions_detail": [{"height": 152, "width": 134}],
            }
        ],
        "config": {"iiif_url": _IIIF_URL},
    }
    respx_mock.get(_SEARCH_URL).mock(return_value=httpx.Response(200, json=payload))
    provider = AicProvider(async_client)

    results = await provider.search("starry", limit=20)

    assert len(results) == 1
    assert results[0].id == "aic:129884"
    assert results[0].height_cm == 152


_LIST_URL = "https://api.artic.edu/api/v1/artworks"


async def test_browse_uses_the_plain_listing_endpoint_with_no_query(respx_mock, async_client):
    payload = {
        "data": [
            {
                "id": 129884,
                "title": "Starry Night and the Astronauts",
                "date_display": "1972",
                "image_id": "e966799b-97ee-1cc6-bd2f-a94b4b8bb8f9",
                "dimensions_detail": [{"height": 152, "width": 134}],
            }
        ],
        "config": {"iiif_url": _IIIF_URL},
    }
    route = respx_mock.get(_LIST_URL).mock(return_value=httpx.Response(200, json=payload))
    provider = AicProvider(async_client)

    results = await provider.browse(limit=20, offset=0)

    assert len(results) == 1
    assert "q" not in route.calls.last.request.url.params


async def test_browse_computes_page_from_offset_and_limit(respx_mock, async_client):
    route = respx_mock.get(_LIST_URL).mock(
        return_value=httpx.Response(200, json={"data": [], "config": {}})
    )
    provider = AicProvider(async_client)

    await provider.browse(limit=20, offset=40)

    assert route.calls.last.request.url.params["page"] == "3"


async def test_browse_drops_items_with_no_image(respx_mock, async_client):
    payload = {
        "data": [
            {"id": 1, "title": "No image", "date_display": None, "image_id": None},
            {
                "id": 2,
                "title": "Has image",
                "date_display": None,
                "image_id": "e966799b-97ee-1cc6-bd2f-a94b4b8bb8f9",
            },
        ],
        "config": {"iiif_url": _IIIF_URL},
    }
    respx_mock.get(_LIST_URL).mock(return_value=httpx.Response(200, json=payload))
    provider = AicProvider(async_client)

    results = await provider.browse(limit=20, offset=0)

    assert [r.id for r in results] == ["aic:2"]
