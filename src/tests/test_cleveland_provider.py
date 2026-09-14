import httpx
import pytest

from martevi.providers.adapters.cleveland import ClevelandProvider

_SEARCH_URL = "https://openaccess-api.clevelandart.org/api/artworks/"
_ITEM_URL = "https://openaccess-api.clevelandart.org/api/artworks/130707"

_ARTWORK = {
    "id": 130707,
    "title": "Head of Saint John the Baptist",
    "creation_date": "c. 1550-1650",
    "technique": "oil on canvas",
    "department": "European Painting and Sculpture",
    "culture": ["Spain or Northern Italy, mid 16th - mid 17th century"],
    "description": "Full curatorial prose.",
    "url": "https://clevelandart.org/art/1953.424",
    "images": {
        "web": {"url": "https://example.org/web.jpg"},
        "print": {"url": "https://example.org/print.jpg"},
        "full": {"url": "https://example.org/full.tif"},
    },
    "dimensions": {
        "framed": {"height": 0.806, "width": 1.048},
        "unframed": {"height": 0.5, "width": 0.752},
    },
}


async def test_get_item_converts_meters_to_cm_and_prefers_unframed(respx_mock, async_client):
    respx_mock.get(_ITEM_URL).mock(return_value=httpx.Response(200, json={"data": _ARTWORK}))
    provider = ClevelandProvider(async_client)

    artwork = await provider.get_item("130707")

    assert artwork is not None
    assert artwork.height_cm == 50.0
    assert artwork.width_cm == 75.2
    assert artwork.culture == "Spain or Northern Italy, mid 16th - mid 17th century"
    assert artwork.image_url == "https://example.org/print.jpg"  # never the .tif "full" url
    assert artwork.image_zoom_url is None  # no IIIF


@pytest.mark.parametrize(
    "culture,expected",
    [
        pytest.param(
            ["Spain or Northern Italy, mid 16th - mid 17th century"],
            "Spain or Northern Italy, mid 16th - mid 17th century",
            id="non-empty-array-uses-first-entry",
        ),
        pytest.param([], None, id="empty-array-becomes-none"),
    ],
)
async def test_get_item_culture_normalization(respx_mock, async_client, culture, expected):
    artwork = {**_ARTWORK, "culture": culture}
    respx_mock.get(_ITEM_URL).mock(return_value=httpx.Response(200, json={"data": artwork}))
    provider = ClevelandProvider(async_client)

    result = await provider.get_item("130707")

    assert result is not None
    assert result.culture == expected


async def test_search_returns_full_objects_inline(respx_mock, async_client):
    respx_mock.get(_SEARCH_URL).mock(return_value=httpx.Response(200, json={"data": [_ARTWORK]}))
    provider = ClevelandProvider(async_client)

    results = await provider.search("saint", limit=20)

    assert len(results) == 1
    assert results[0].id == "cleveland:130707"


async def test_browse_uses_has_image_filter_and_native_skip_offset(respx_mock, async_client):
    route = respx_mock.get(_SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"data": [_ARTWORK]})
    )
    provider = ClevelandProvider(async_client)

    results = await provider.browse(limit=20, offset=40)

    assert len(results) == 1
    assert route.calls.last.request.url.params["has_image"] == "1"
    assert route.calls.last.request.url.params["skip"] == "40"
    assert "q" not in route.calls.last.request.url.params
