import os

import httpx

from martevi.providers.adapters import (
    AicProvider,
    ClevelandProvider,
    HarvardProvider,
    MetProvider,
    RijksmuseumProvider,
    SmithsonianProvider,
    VamProvider,
)
from martevi.providers.base import MuseumProvider
from martevi.providers.translating import TranslatingProvider
from martevi.translation import ArgosTranslator


def build_registry(client: httpx.AsyncClient) -> dict[str, MuseumProvider]:
    translator = ArgosTranslator("en", "pt")  # outbound result fields
    query_translator = ArgosTranslator("pt", "en")  # inbound queries
    adapters: list[MuseumProvider] = [
        MetProvider(client),
        AicProvider(client),
        ClevelandProvider(client),
        HarvardProvider(client, api_key=os.environ.get("HARVARD_API_KEY", "")),
        RijksmuseumProvider(client),
        SmithsonianProvider(client, api_key=os.environ.get("SMITHSONIAN_API_KEY") or "DEMO_KEY"),
        VamProvider(client),
    ]
    return {adapter.provider_id: TranslatingProvider(adapter, translator) for adapter in adapters}
