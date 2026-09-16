import httpx

from martevi.providers.adapters.smithsonian import SmithsonianProvider

_SEARCH_URL = "https://api.si.edu/openaccess/api/v1.0/search"
_ITEM_URL = "https://api.si.edu/openaccess/api/v1.0/content/edanmdm:saam_1985.66.403_415"

_RECORD = {
    "id": "edanmdm:saam_1985.66.403_415",
    "title": "Some Painting",
    "content": {
        "descriptiveNonRepeating": {
            "title": {"content": "Some Painting"},
            "record_link": "https://americanart.si.edu/collections/search/artwork/?id=18693",
            "online_media": {
                "media": [
                    {
                        "idsId": "SAAM-1985.66.403415_1",
                        "thumbnail": "https://example.org/thumb.jpg",
                        "resources": [
                            {"label": "Screen Image", "url": "https://example.org/screen.jpg"},
                            {"label": "Thumbnail Image", "url": "https://example.org/thumb.jpg"},
                        ],
                    }
                ]
            },
        },
        "freetext": {
            "date": [{"content": "c. 1803-12"}],
            "physicalDescription": [
                {"label": "Medium", "content": "oil on canvas"},
                {"label": "Dimensions", "content": "31.2 x 14.3 cm (12 5/16 x 5 5/8 in)"},
            ],
            "setName": [{"label": "Department", "content": "Painting and Sculpture"}],
        },
        "indexedStructured": {},
    },
}


async def test_get_item_parses_dimensions_and_builds_iiif_manifest(respx_mock, async_client):
    respx_mock.get(_ITEM_URL).mock(return_value=httpx.Response(200, json={"response": _RECORD}))
    provider = SmithsonianProvider(async_client, api_key="DEMO_KEY")

    artwork = await provider.get_item("edanmdm:saam_1985.66.403_415")

    assert artwork is not None
    assert artwork.id == "smithsonian:edanmdm:saam_1985.66.403_415"
    assert artwork.height_cm == 31.2
    assert artwork.width_cm == 14.3
    assert artwork.medium == "oil on canvas"
    assert artwork.department == "Painting and Sculpture"
    assert artwork.description is None  # never uses notes[] / has no description field
    assert artwork.culture is None  # indexedStructured.culture absent on this record
    assert artwork.image_url == "https://example.org/screen.jpg"
    assert artwork.image_zoom_url == "https://ids.si.edu/ids/manifest/SAAM-1985.66.403415_1"
    # thumbnail_url prefers the same "Screen Image" as image_url — EDAN's own
    # "Thumbnail Image" resource is a ~150px crop, too small for a masonry
    # grid card, and made every Smithsonian result look blurry.
    assert artwork.thumbnail_url == "https://example.org/screen.jpg"


async def test_thumbnail_falls_back_to_thumbnail_image_without_a_screen_image(
    respx_mock, async_client
):
    record = {
        **_RECORD,
        "content": {
            **_RECORD["content"],
            "descriptiveNonRepeating": {
                **_RECORD["content"]["descriptiveNonRepeating"],
                "online_media": {
                    "media": [
                        {
                            "idsId": "SAAM-1985.66.403415_1",
                            "thumbnail": "https://example.org/legacy-thumb.jpg",
                            "resources": [
                                {"label": "Thumbnail Image", "url": "https://example.org/thumb.jpg"},
                            ],
                        }
                    ]
                },
            },
        },
    }
    respx_mock.get(_ITEM_URL).mock(return_value=httpx.Response(200, json={"response": record}))
    provider = SmithsonianProvider(async_client, api_key="DEMO_KEY")

    artwork = await provider.get_item("edanmdm:saam_1985.66.403_415")

    assert artwork is not None
    assert artwork.image_url is None  # no "Screen Image" resource on this record
    assert artwork.thumbnail_url == "https://example.org/thumb.jpg"


async def test_thumbnail_falls_back_to_legacy_thumbnail_field_last(respx_mock, async_client):
    record = {
        **_RECORD,
        "content": {
            **_RECORD["content"],
            "descriptiveNonRepeating": {
                **_RECORD["content"]["descriptiveNonRepeating"],
                "online_media": {
                    "media": [
                        {
                            "idsId": "SAAM-1985.66.403415_1",
                            "thumbnail": "https://example.org/legacy-thumb.jpg",
                            "resources": [],
                        }
                    ]
                },
            },
        },
    }
    respx_mock.get(_ITEM_URL).mock(return_value=httpx.Response(200, json={"response": record}))
    provider = SmithsonianProvider(async_client, api_key="DEMO_KEY")

    artwork = await provider.get_item("edanmdm:saam_1985.66.403_415")

    assert artwork is not None
    assert artwork.thumbnail_url == "https://example.org/legacy-thumb.jpg"


async def test_get_item_absent_online_media_key_yields_none_image(respx_mock, async_client):
    record = {
        **_RECORD,
        "content": {
            **_RECORD["content"],
            "descriptiveNonRepeating": {
                "title": {"content": "Some Painting"},
                "record_link": None,
                # online_media key entirely absent, not an empty dict/list.
            },
        },
    }
    respx_mock.get(_ITEM_URL).mock(return_value=httpx.Response(200, json={"response": record}))
    provider = SmithsonianProvider(async_client, api_key="DEMO_KEY")

    artwork = await provider.get_item("edanmdm:saam_1985.66.403_415")

    assert artwork is not None
    assert artwork.image_url is None
    assert artwork.image_zoom_url is None


async def test_search_returns_full_rows_and_uses_demo_key_fallback(respx_mock, async_client):
    payload = {"response": {"rows": [_RECORD]}}
    respx_mock.get(_SEARCH_URL).mock(return_value=httpx.Response(200, json=payload))
    provider = SmithsonianProvider(async_client, api_key="DEMO_KEY")

    results = await provider.search("painting", limit=10)

    assert len(results) == 1
    assert results[0].id == "smithsonian:edanmdm:saam_1985.66.403_415"


async def test_browse_uses_broad_query_and_native_start_offset(respx_mock, async_client):
    payload = {"response": {"rows": [_RECORD]}}
    route = respx_mock.get(_SEARCH_URL).mock(return_value=httpx.Response(200, json=payload))
    provider = SmithsonianProvider(async_client, api_key="DEMO_KEY")

    results = await provider.browse(limit=10, offset=20)

    assert len(results) == 1
    assert route.calls.last.request.url.params["start"] == "20"
    assert route.calls.last.request.url.params["rows"] == "10"
