from martevi.providers import MuseumProvider, TranslatingProvider
from martevi.schema import Artwork, ArtworkSummary


class FakeTranslator:
    """Deterministic test double: prefixes text so tests can assert exactly what was translated."""

    def __init__(self, prefix: str = "PT::") -> None:
        self._prefix = prefix
        self.calls: list[str] = []

    async def translate(self, text: str) -> str:
        self.calls.append(text)
        return f"{self._prefix}{text}"


class FakeProvider:
    """In-memory MuseumProvider test double."""

    def __init__(
        self,
        provider_id: str,
        summaries: list[ArtworkSummary],
        items: dict[str, Artwork],
    ) -> None:
        self.provider_id = provider_id
        self._summaries = summaries
        self._items = items

    async def search(self, query: str, limit: int = 20) -> list[ArtworkSummary]:
        return self._summaries[:limit]

    async def get_item(self, external_id: str) -> Artwork | None:
        return self._items.get(external_id)


def _full_artwork() -> Artwork:
    return Artwork(
        id="met:436535",
        provider_id="met",
        title="Wheat Field with Cypresses",
        date="1889",
        thumbnail_url="https://example.org/thumb.jpg",
        height_cm=73.2,
        width_cm=93.4,
        description="A wall note about the painting.",
        medium="Oil on canvas",
        culture="Dutch",
        department="European Paintings",
        image_url="https://example.org/full.jpg",
        image_zoom_url="https://example.org/iiif",
        source_url="https://example.org/436535",
    )


def _artwork_with_missing_fields() -> Artwork:
    return Artwork(
        id="met:1",
        provider_id="met",
        title="Untitled",
        date=None,
        thumbnail_url=None,
        height_cm=None,
        width_cm=None,
        description=None,
        medium=None,
        culture=None,
        department=None,
        image_url=None,
        image_zoom_url=None,
        source_url=None,
    )


def _summary() -> ArtworkSummary:
    return ArtworkSummary(
        id="met:436535",
        provider_id="met",
        title="Wheat Field with Cypresses",
        date="1889",
        thumbnail_url="https://example.org/thumb.jpg",
        height_cm=73.2,
        width_cm=93.4,
    )


async def test_search_translates_title():
    provider = FakeProvider("met", [_summary()], {})
    translating = TranslatingProvider(provider, FakeTranslator())

    results = await translating.search("wheat", limit=20)

    assert results[0].title == "PT::Wheat Field with Cypresses"


async def test_search_leaves_non_translatable_summary_fields_untouched():
    original = _summary()
    provider = FakeProvider("met", [original], {})
    translating = TranslatingProvider(provider, FakeTranslator())

    result = (await translating.search("wheat", limit=20))[0]

    assert result.id == original.id
    assert result.provider_id == original.provider_id
    assert result.date == original.date
    assert result.thumbnail_url == original.thumbnail_url
    assert result.height_cm == original.height_cm
    assert result.width_cm == original.width_cm


async def test_get_item_translates_title_description_medium_culture():
    original = _full_artwork()
    provider = FakeProvider("met", [], {original.id: original})
    translating = TranslatingProvider(provider, FakeTranslator())

    result = await translating.get_item(original.id)

    assert result is not None
    assert result.title == f"PT::{original.title}"
    assert result.description == f"PT::{original.description}"
    assert result.medium == f"PT::{original.medium}"
    assert result.culture == f"PT::{original.culture}"


async def test_get_item_leaves_non_translatable_artwork_fields_untouched():
    original = _full_artwork()
    provider = FakeProvider("met", [], {original.id: original})
    translating = TranslatingProvider(provider, FakeTranslator())

    result = await translating.get_item(original.id)

    assert result is not None
    assert result.id == original.id
    assert result.provider_id == original.provider_id
    assert result.date == original.date
    assert result.thumbnail_url == original.thumbnail_url
    assert result.height_cm == original.height_cm
    assert result.width_cm == original.width_cm
    assert result.department == original.department
    assert result.image_url == original.image_url
    assert result.image_zoom_url == original.image_zoom_url
    assert result.source_url == original.source_url


async def test_get_item_preserves_none_for_missing_translatable_fields():
    original = _artwork_with_missing_fields()
    provider = FakeProvider("met", [], {original.id: original})
    translator = FakeTranslator()
    translating = TranslatingProvider(provider, translator)

    result = await translating.get_item(original.id)

    assert result is not None
    assert result.description is None
    assert result.medium is None
    assert result.culture is None
    assert translator.calls == ["Untitled"]


async def test_get_item_returns_none_when_wrapped_provider_returns_none():
    provider = FakeProvider("met", [], {})
    translating = TranslatingProvider(provider, FakeTranslator())

    result = await translating.get_item("does-not-exist")

    assert result is None


async def test_search_preserves_result_count_and_order():
    first = _summary()
    second = ArtworkSummary(
        id="met:2",
        provider_id="met",
        title="Second",
        date=None,
        thumbnail_url=None,
        height_cm=None,
        width_cm=None,
    )
    provider = FakeProvider("met", [first, second], {})
    translating = TranslatingProvider(provider, FakeTranslator())

    results = await translating.search("query", limit=20)

    assert [r.id for r in results] == [first.id, second.id]


async def test_provider_id_delegates_to_wrapped_provider():
    provider = FakeProvider("met", [], {})
    translating = TranslatingProvider(provider, FakeTranslator())

    assert translating.provider_id == provider.provider_id


async def test_translating_provider_satisfies_museum_provider_protocol():
    provider = FakeProvider("met", [], {})
    translating = TranslatingProvider(provider, FakeTranslator())

    assert isinstance(translating, MuseumProvider)


async def test_double_wrapping_composes():
    original = _full_artwork()
    provider = FakeProvider("met", [], {original.id: original})
    inner = TranslatingProvider(provider, FakeTranslator(prefix="INNER::"))
    outer = TranslatingProvider(inner, FakeTranslator(prefix="OUTER::"))

    assert isinstance(outer, MuseumProvider)

    result = await outer.get_item(original.id)

    assert result is not None
    assert result.title == f"OUTER::INNER::{original.title}"
