import asyncio
import logging
from typing import TypeVar

from martevi.providers._internal.concurrency import gather_ordered
from martevi.providers.base import MuseumProvider
from martevi.schema import Artwork, ArtworkSummary
from martevi.translation.base import Translator

logger = logging.getLogger(__name__)

TRANSLATABLE_FIELDS: tuple[str, ...] = ("title", "description", "medium", "culture")

T = TypeVar("T", bound=ArtworkSummary)


class TranslatingProvider:
    """Decorates a MuseumProvider, translating only allowlisted free-text fields (GoF Decorator)."""

    def __init__(
        self,
        provider: MuseumProvider,
        translator: Translator,
        query_translator: Translator | None = None,
    ) -> None:
        self._provider = provider
        self._translator = translator
        # Optional reverse-direction (target->source) translator for search queries —
        # see search()'s zero-result retry. None means query translation is disabled,
        # matching every existing two-arg construction of this class.
        self._query_translator = query_translator
        self.provider_id = provider.provider_id

    async def search(self, query: str, limit: int = 20) -> list[ArtworkSummary]:
        summaries = await self._provider.search(query, limit)
        if not summaries and self._query_translator is not None:
            # Try the query as typed first (so "Van Gogh" isn't mangled); only fall
            # back to a translated retry if that genuinely found nothing. Handles
            # Portuguese search terms without a language-detection dependency.
            try:
                translated_query = await self._query_translator.translate(query)
            except Exception as exc:
                # Same reasoning as _translate_field below: the translation backend
                # is an unofficial, no-SLA dependency — one flaky call must not 500
                # the whole search. Fall back to the untranslated (already-empty)
                # result rather than raising.
                logger.warning(
                    "Query translation failed for %r (provider=%r): %s: %s; using original query.",
                    query,
                    self.provider_id,
                    type(exc).__name__,
                    exc,
                )
                translated_query = query
            if translated_query.strip().casefold() != query.strip().casefold():
                summaries = await self._provider.search(translated_query, limit)
        # Only "title" ever reaches the frontend from search() (ArtworkSummary has no
        # description/medium/culture) — a couple of adapters (Met, Rijksmuseum) return
        # full Artwork objects internally since they have no lightweight summary
        # endpoint of their own, which would otherwise translate 3 fields per result
        # nobody's going to see. Given MyMemory's real-world 5 req/s cap, that's not
        # free — restrict to what search results actually use.
        return await gather_ordered(
            (self._translate(summary, fields=("title",)) for summary in summaries),
            max_concurrency=10,
        )

    async def browse(self, limit: int = 20, offset: int = 0) -> list[ArtworkSummary]:
        summaries = await self._provider.browse(limit, offset)
        return await gather_ordered(
            (self._translate(summary, fields=("title",)) for summary in summaries),
            max_concurrency=10,
        )

    async def get_item(self, external_id: str) -> Artwork | None:
        artwork = await self._provider.get_item(external_id)
        if artwork is None:
            return None
        return await self._translate(artwork)

    async def _translate(self, model: T, fields: tuple[str, ...] = TRANSLATABLE_FIELDS) -> T:
        applicable = [field for field in fields if field in type(model).model_fields]
        updates = dict(
            await asyncio.gather(*(self._translate_field(model, field) for field in applicable))
        )
        return model.model_copy(update=updates)

    async def _translate_field(self, model: T, field: str) -> tuple[str, str | None]:
        value = getattr(model, field)
        if value is None:
            return field, None
        try:
            return field, await self._translator.translate(value)
        except Exception as exc:
            # The translation backend is an unofficial, no-SLA dependency (see
            # CHANGELOG.md) — one flaky call must not 500 the whole request. Fall
            # back to the original, untranslated text instead.
            logger.warning(
                "Translation failed for field %r on %r (provider=%r): %s: %s; using original text.",
                field,
                model.id,
                self.provider_id,
                type(exc).__name__,
                exc,
            )
            return field, value
