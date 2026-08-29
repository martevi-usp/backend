import httpx

from martevi.providers.adapters.harvard import HarvardProvider

_SEARCH_URL = "https://api.harvardartmuseums.org/object"
_ITEM_URL = "https://api.harvardartmuseums.org/object/304069"

_OBJECT = {
    "id": 304069,
    "title": "Hydria (water jar) with Siren Attachment",
    "dated": "late 5th century BCE",
    "culture": "Greek",
    "period": "Classical period, High",
    "medium": "Bronze, traces of silvering and possible gilding",
    "dimensions": "h. 41.9 cm x diam. 28.5 cm (37 cm in diam. with handles)",
    "department": "Department of Ancient and Byzantine Art & Numismatics",
    "description": "",
    "commentary": "",
    "labeltext": None,
    "url": "https://www.harvardartmuseums.org/collections/object/304069",
    "primaryimageurl": "https://nrs.harvard.edu/urn-3:HUAM:DDC251092_dynmc",
    "seeAlso": [
        {
            "id": "https://iiif.harvardartmuseums.org/manifests/object/304069",
            "type": "IIIF Manifest",
        }
    ],
}


async def test_get_item_bails_on_diam_only_dimensions_and_falls_back_description(
    respx_mock, async_client
):
    respx_mock.get(_ITEM_URL).mock(return_value=httpx.Response(200, json=_OBJECT))
    provider = HarvardProvider(async_client, api_key="test-key")

    artwork = await provider.get_item("304069")

    assert artwork is not None
    # No "w." label present — parse_labeled must bail rather than guess.
    assert artwork.height_cm is None
    assert artwork.width_cm is None
    assert artwork.culture == "Greek"
    # labeltext=None, description="" and commentary="" are all blank — must fall
    # through to None since there's no contextualtext either.
    assert artwork.description is None
    assert artwork.image_zoom_url == "https://iiif.harvardartmuseums.org/manifests/object/304069"
    assert (
        artwork.image_url
        == "https://nrs.harvard.edu/urn-3:HUAM:DDC251092_dynmc/full/full/0/default.jpg"
    )


async def test_get_item_culture_falls_back_to_period_when_blank(respx_mock, async_client):
    obj = {**_OBJECT, "culture": ""}
    respx_mock.get(_ITEM_URL).mock(return_value=httpx.Response(200, json=obj))
    provider = HarvardProvider(async_client, api_key="test-key")

    artwork = await provider.get_item("304069")

    assert artwork is not None
    assert artwork.culture == "Classical period, High"


async def test_search_passes_fields_param_and_normalizes_records(respx_mock, async_client):
    respx_mock.get(_SEARCH_URL).mock(return_value=httpx.Response(200, json={"records": [_OBJECT]}))
    provider = HarvardProvider(async_client, api_key="test-key")

    results = await provider.search("hydria", limit=10)

    assert len(results) == 1
    assert results[0].id == "harvard:304069"
