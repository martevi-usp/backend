from typing import TypeVar

from martevi.providers.base import MuseumProvider
from martevi.schema import Artwork, ArtworkSummary
from martevi.translation.base import Translator

TRANSLATABLE_FIELDS: tuple[str, ...] = ("title", "description", "medium", "culture")

T = TypeVar("T", bound=ArtworkSummary)


class TranslatingProvider:
    """Decorates a MuseumProvider, translating only allowlisted free-text fields (GoF Decorator)."""

    def __init__(self, provider: MuseumProvider, translator: Translator) -> None:
        self._provider = provider
        self._translator = translator
        self.provider_id = provider.provider_id

    async def search(self, query: str, limit: int = 20) -> list[ArtworkSummary]:
        summaries = await self._provider.search(query, limit)
        return [await self._translate(summary) for summary in summaries]

    async def get_item(self, external_id: str) -> Artwork | None:
        artwork = await self._provider.get_item(external_id)
        if artwork is None:
            return None
        return await self._translate(artwork)

    async def _translate(self, model: T) -> T:
        updates: dict[str, str | None] = {}
        for field in TRANSLATABLE_FIELDS:
            if field not in type(model).model_fields:
                continue
            value = getattr(model, field)
            updates[field] = await self._translator.translate(value) if value is not None else None
        return model.model_copy(update=updates)
