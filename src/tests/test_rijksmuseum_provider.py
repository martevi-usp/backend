import httpx

from martevi.providers.adapters.rijksmuseum import RijksmuseumProvider

_SEARCH_URL = "https://data.rijksmuseum.nl/search/collection"
_RESOLVE_URL = "https://id.rijksmuseum.nl/200105339"

_RESOLVED = {
    "aggregatedCHO": {
        "title": {"nl": "Schoolklas meisjes met begeleidsters"},
        "created": [
            {"@language": "en", "@value": "1895 - 1900"},
            {"@language": "nl", "@value": "1895 - 1900"},
        ],
        "extent": [
            {"@language": "en", "@value": "height 154 mm x width 265 mm"},
            {"@language": "nl", "@value": "hoogte 154 mm x breedte 265 mm"},
        ],
        "medium": [
            {
                "http://www.w3.org/2004/02/skos/core#prefLabel": [
                    {"@language": "en", "@value": "ink"}
                ]
            },
            {
                "http://www.w3.org/2004/02/skos/core#prefLabel": [
                    {"@language": "en", "@value": "paper"}
                ]
            },
        ],
    },
    "isShownAt": {"id": "https://www.rijksmuseum.nl/nl/collectie/object/RP-T-00-808"},
    "isShownBy": {
        "id": "https://iiif.micr.io/oZsQW/full/max/0/default.jpg",
        "http://rdfs.org/sioc/services#has_service": {"id": "https://iiif.micr.io/oZsQW"},
    },
}


async def test_get_item_converts_mm_to_cm_and_falls_back_title_language(respx_mock, async_client):
    respx_mock.get(_RESOLVE_URL, params={"_profile": "edm-framed"}).mock(
        return_value=httpx.Response(200, json=_RESOLVED)
    )
    provider = RijksmuseumProvider(async_client)

    artwork = await provider.get_item("200105339")

    assert artwork is not None
    assert artwork.id == "rijksmuseum:200105339"
    # No "en" key present — must fall back to "nl".
    assert artwork.title == "Schoolklas meisjes met begeleidsters"
    assert artwork.height_cm == 15.4
    assert artwork.width_cm == 26.5
    assert artwork.medium == "ink, paper"
    assert artwork.culture is None
    assert artwork.department is None
    assert artwork.image_url == "https://iiif.micr.io/oZsQW/full/max/0/default.jpg"
    assert artwork.image_zoom_url == "https://iiif.micr.io/oZsQW"
    assert artwork.source_url == "https://www.rijksmuseum.nl/nl/collectie/object/RP-T-00-808"


async def test_search_extracts_numeric_id_and_fans_out(respx_mock, async_client):
    payload = {
        "orderedItems": [
            {"id": "https://id.rijksmuseum.nl/200105339", "type": "HumanMadeObject"},
        ]
    }
    respx_mock.get(_SEARCH_URL).mock(return_value=httpx.Response(200, json=payload))
    respx_mock.get(_RESOLVE_URL, params={"_profile": "edm-framed"}).mock(
        return_value=httpx.Response(200, json=_RESOLVED)
    )
    provider = RijksmuseumProvider(async_client)

    results = await provider.search("schoolklas", limit=20)

    assert len(results) == 1
    assert results[0].id == "rijksmuseum:200105339"


async def test_browse_delegates_to_search_with_a_broad_dutch_term(respx_mock, async_client):
    # No numeric offset in the new Linked Art API (opaque pageTokens only, see
    # browse()'s comment) — delegates to search() with "de" (Dutch "the/of",
    # broad enough to browse) and reslices client-side.
    payload = {
        "orderedItems": [
            {"id": "https://id.rijksmuseum.nl/200105339", "type": "HumanMadeObject"},
        ]
    }
    search_route = respx_mock.get(_SEARCH_URL).mock(return_value=httpx.Response(200, json=payload))
    respx_mock.get(_RESOLVE_URL, params={"_profile": "edm-framed"}).mock(
        return_value=httpx.Response(200, json=_RESOLVED)
    )
    provider = RijksmuseumProvider(async_client)

    results = await provider.browse(limit=20, offset=0)

    assert len(results) == 1
    assert search_route.calls.last.request.url.params["title"] == "de"
