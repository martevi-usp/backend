import asyncio

import argostranslate.translate as argos_translate
import stanza
from argostranslate import sbd as argos_sbd

# Argos Translate has no pt-BR/pt-PT distinction — just "pt". Accepted as a
# known simplification (same spirit as this project's other documented
# approximations, e.g. EDAN's free-text dimensions) rather than a bug.

# Argos's sentence-boundary-detector is Stanza, and Stanza's default
# Pipeline(...) call hardcodes download_method=DOWNLOAD_RESOURCES — it always
# tries to fetch resources.json from raw.githubusercontent.com, even when the
# package (and that same resources.json) is already installed locally. That
# breaks the whole point of ADR-0002 (zero network at request time), so this
# patches Stanza to reuse whatever resources.json is already cached under the
# installed package's own stanza/ subdirectory instead of re-fetching it.
# REUSE_RESOURCES only *skips the fetch*, it doesn't relax the schema Stanza
# expects — the cached file must already be a complete, current-schema
# resources.json. install_translation_models.py guarantees that by running an
# actual translate() in both directions (not just package.install_from_path,
# which never touches Stanza) at Docker build time, while the network is
# still available, before this patch is ever exercised against a sealed image.
_original_lazy_pipeline = argos_sbd.StanzaSentencizer.lazy_pipeline


def _offline_lazy_pipeline(self: argos_sbd.StanzaSentencizer) -> stanza.Pipeline:
    if self.stanza_pipeline is None:
        self.stanza_pipeline = stanza.Pipeline(
            lang=self.stanza_lang_code,
            dir=str(self.pkg.package_path / "stanza"),
            processors="tokenize",
            use_gpu=False,
            logging_level="WARNING",
            download_method=stanza.DownloadMethod.REUSE_RESOURCES,
        )
    return self.stanza_pipeline


argos_sbd.StanzaSentencizer.lazy_pipeline = _offline_lazy_pipeline


class ArgosTranslator:
    """Translator backed by Argos Translate — a real, fully offline neural MT
    engine (CTranslate2 under the hood). Runs in-process with zero network calls
    once its language-pair model is installed (see
    ../../scripts/install_translation_models.py, run at Docker build time so the
    running container never needs network access for this at all).

    Replaces the earlier MyMemory-backed DeepTranslatorTranslator (ADR-0001),
    which had a real, unofficial 5 req/s ceiling that a large fan-out search
    could exceed under real traffic — see ADR-0002. Reversing that decision
    trades network latency + rate-limit risk for local CPU inference (roughly
    40ms/title once the model is warm, confirmed empirically) and a larger
    Docker image (~80MB per language-pair model).
    """

    def __init__(self, source: str, target: str) -> None:
        self._source = source
        self._target = target
        # Per-instance, unbounded, process-lifetime cache — same reasoning as the
        # translator this replaces: this process only ever handles a small,
        # repeated vocabulary (search suggestion chips, common titles), and
        # translation is deterministic. Cheaper than the MyMemory-era cache was
        # (no rate limit to protect), but still saves real CPU time on repeats.
        self._cache: dict[str, str] = {}

    async def translate(self, text: str) -> str:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        # Blocking, CPU-bound (CTranslate2 inference) — must not run on the
        # event loop thread. to_thread lets multiple concurrent translate()
        # calls actually run in parallel (CTranslate2 releases the GIL during
        # the C++ inference itself, same as numpy).
        result = await asyncio.to_thread(
            argos_translate.translate, text, self._source, self._target
        )
        self._cache[text] = result
        return result
