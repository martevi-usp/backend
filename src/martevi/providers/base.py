from typing import Protocol, runtime_checkable

from martevi.schema import Artwork, ArtworkSummary


@runtime_checkable
class MuseumProvider(Protocol):
    """Common interface every museum Adapter implements."""

    provider_id: str

    async def search(self, query: str, limit: int = 20) -> list[ArtworkSummary]:
        ...

    async def get_item(self, external_id: str) -> Artwork | None:
        ...

    async def browse(self, limit: int = 20, offset: int = 0) -> list[ArtworkSummary]:
        """A query-less page of the collection, newest/most-notable-first where the
        provider has such a concept — used to show art before anyone searches."""
        ...
