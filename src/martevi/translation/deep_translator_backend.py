import asyncio

from deep_translator import GoogleTranslator


class DeepTranslatorTranslator:
    """Translator backed by deep-translator's GoogleTranslator, offloaded off the event loop."""

    def __init__(self, source: str = "en", target: str = "pt") -> None:
        self._client = GoogleTranslator(source=source, target=target)

    async def translate(self, text: str) -> str:
        return await asyncio.to_thread(self._client.translate, text)
