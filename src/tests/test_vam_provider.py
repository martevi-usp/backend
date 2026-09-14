import httpx

from martevi.providers.adapters.vam import VamProvider

_SEARCH_URL = "https://api.vam.ac.uk/v2/objects/search"
_ITEM_URL = "https://api.vam.ac.uk/v2/museumobject/O94917"

_ITEM = {
    "meta": {"_links": {"collection_page": {"href": "https://collections.vam.ac.uk/item/O94917/"}}},
    "record": {
        "systemNumber": "O94917",
        "titles": [{"title": "Teapot", "type": "generic title"}],
        "productionDates": [{"date": {"text": "1922-1923"}}],
        "materials": [{"text": "silver"}, {"text": "wood"}],
        "styles": [{"text": "Modernist"}],
        "categories": [{"text": "Metalwork"}],
        "summaryDescription": "Full curatorial history.",
        "briefDescription": "A teapot.",
        "dimensions": [
            {"dimension": "Height", "value": "13.2", "unit": "cm"},
            {"dimension": "Width", "value": "20.5", "unit": "cm"},
            {"dimension": "Weight", "value": "500", "unit": "g"},
        ],
        # The real API's shape: a bare list of image ids, not an `_images` dict —
        # confirmed against a live GET /v2/museumobject/{id} response.
        "images": ["2006BG1640"],
    },
}


async def test_get_item_uses_structured_cm_dimensions_no_regex_needed(respx_mock, async_client):
    respx_mock.get(_ITEM_URL).mock(return_value=httpx.Response(200, json=_ITEM))
    provider = VamProvider(async_client)

    artwork = await provider.get_item("O94917")

    assert artwork is not None
    assert artwork.height_cm == 13.2
    assert artwork.width_cm == 20.5  # the "g" (grams) weight entry must be ignored
    assert artwork.culture == "Modernist"  # judgment-call substitute via styles[0]
    assert artwork.department == "Metalwork"
    assert artwork.description == "Full curatorial history."
    assert artwork.image_zoom_url == "https://framemark.vam.ac.uk/collections/2006BG1640/"
    assert (
        artwork.image_url
        == "https://framemark.vam.ac.uk/collections/2006BG1640/full/full/0/default.jpg"
    )
    assert (
        artwork.thumbnail_url
        == "https://framemark.vam.ac.uk/collections/2006BG1640/full/400,/0/default.jpg"
    )
    assert artwork.source_url == "https://collections.vam.ac.uk/item/O94917/"


async def test_search_summaries_have_no_dimensions(respx_mock, async_client):
    payload = {
        "records": [
            {
                "systemNumber": "O94917",
                "_primaryTitle": "Teapot",
                "_primaryDate": "1922-1923",
                "_primaryImageId": "2006BG1640",
                # The real API's `_images._primary_thumbnail` (a fixed 100x100 crop)
                # is deliberately NOT used — see VamProvider._to_summary.
                "_images": {"_primary_thumbnail": "https://example.org/thumb-100x100.jpg"},
            }
        ]
    }
    respx_mock.get(_SEARCH_URL).mock(return_value=httpx.Response(200, json=payload))
    provider = VamProvider(async_client)

    results = await provider.search("teapot", limit=20)

    assert len(results) == 1
    assert results[0].id == "vam:O94917"
    assert (
        results[0].thumbnail_url
        == "https://framemark.vam.ac.uk/collections/2006BG1640/full/400,/0/default.jpg"
    )
    assert results[0].height_cm is None
    assert results[0].width_cm is None


async def test_browse_uses_images_exist_filter_and_computes_page(respx_mock, async_client):
    payload = {
        "records": [
            {
                "systemNumber": "O94917",
                "_primaryTitle": "Teapot",
                "_primaryImageId": "2006BG1640",
            }
        ]
    }
    route = respx_mock.get(_SEARCH_URL).mock(return_value=httpx.Response(200, json=payload))
    provider = VamProvider(async_client)

    results = await provider.browse(limit=20, offset=40)

    assert len(results) == 1
    assert route.calls.last.request.url.params["images_exist"] == "1"
    assert route.calls.last.request.url.params["page"] == "3"
    assert "q" not in route.calls.last.request.url.params


async def test_search_summary_has_no_thumbnail_when_object_has_no_image_id():
    payload = {
        "records": [
            {
                "systemNumber": "O1",
                "_primaryTitle": "Untitled",
            }
        ]
    }
    provider = VamProvider(None)  # not used — no HTTP call needed for this assertion path

    result = provider._to_summary(payload["records"][0])

    assert result.thumbnail_url is None
