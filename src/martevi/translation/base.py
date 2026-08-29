from typing import Protocol, runtime_checkable


@runtime_checkable
class Translator(Protocol):
    """Translates free text from a source language to a target language fixed at construction."""

    async def translate(self, text: str) -> str:
        ...
