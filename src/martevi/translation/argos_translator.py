import asyncio
import threading

try:
    import argostranslate.translate as argos_translate
except ModuleNotFoundError as exc:
    _ARGOS_IMPORT_ERROR = exc

    class _ArgosTranslateUnavailable:
        @staticmethod
        def translate(*args, **kwargs):
            raise ModuleNotFoundError(
                "argostranslate is required to run translations. "
                "Install argostranslate (with its runtime setup) before using ArgosTranslator."
            ) from _ARGOS_IMPORT_ERROR

    argos_translate = _ArgosTranslateUnavailable()

# Argos Translate has no pt-BR/pt-PT distinction — just "pt". Accepted as a
# known simplification (same spirit as this project's other documented
# approximations, e.g. EDAN's free-text dimensions) rather than a bug.

# Argos builds each language pair's CTranslate2 model lazily on its first
# translate() call, with no lock. Under a fan-out search dozens of to_thread
# calls hit a cold pair at once, each builds its own copy of the model, and
# the process peaked near 2 GB (measured in a 512 MB container: OOM-killed).
# Serialising only the *first* call per pair loads each model exactly once;
# everything after runs concurrently, since CTranslate2 releases the GIL.
_load_lock = threading.Lock()
_loaded: set[tuple[str, str]] = set()


def _translate_blocking(text: str, source: str, target: str) -> str:
    pair = (source, target)
    if pair not in _loaded:
        with _load_lock:
            if pair not in _loaded:
                result = argos_translate.translate(text, source, target)
                _loaded.add(pair)
                return result
    return argos_translate.translate(text, source, target)


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
            _translate_blocking, text, self._source, self._target
        )
        self._cache[text] = result
        return result
