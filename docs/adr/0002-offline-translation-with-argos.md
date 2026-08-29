# ADR-0002: Offline Translation with Argos Translate

**Status:** Accepted
**Date:** 2026-09-13
**Deciders:** martevi backend owner(s)

## Context

ADR-0001 chose `deep-translator`'s unofficial MyMemory backend for V1, explicitly flagging the risk: "unofficial/reverse-engineered Google endpoint — no SLA, can break or get IP-throttled if traffic grows" — and named its own trigger for revisiting that choice, under Option D (Argos Translate): "Worth revisiting only if network-dependent translation becomes a reliability problem in production."

That trigger has now fired. Real fan-out traffic against `TranslatingProvider` produced repeated request failures of this shape:

```
Translation failed for field 'title' on 'met:206989' (provider='met'): TooManyRequests:
Server Error: You made too many requests to the server. According to google, you are
allowed to make 5 requests per second and up to 200k requests per day. You can wait
and try again later or you can try the translate_batch function; using original text.
```

MyMemory's real ceiling — 5 req/s — is well below what a single cross-museum fan-out search needs: one request can require translating dozens of distinct, never-before-seen titles across up to 7 providers concurrently. The existing per-instance cache and shared rate limiter (added before this ADR) reduce repeat calls but can't help on a genuinely large batch of new titles, which is exactly what real search traffic produces. The existing fallback (log a warning, keep the original English text — see ADR-0001's Trade-off Analysis) means this doesn't 500, but it does mean users see untranslated titles under load, which is the user-facing symptom this ADR fixes.

## Decision

Replace `deep-translator`/MyMemory with **Argos Translate** — a real, open-source neural MT engine (CTranslate2 under the hood) that runs fully in-process, with zero network calls at request time once its language-pair models are installed.

- `ArgosTranslator` (`backend/src/martevi/translation/argos_translator.py`) implements the same `Translator` protocol ADR-0001 already defined (`async def translate(text: str) -> str`), so `TranslatingProvider` needs no changes at all — it depends only on that protocol.
- Model installation happens once, at **Docker build time** (`backend/src/scripts/install_translation_models.py`, invoked from a `RUN` step in `backend/Dockerfile`'s `base` stage), not at container startup or on first request — the built image already has both `en→pt` and `pt→en` models baked in, so the running container is fully offline for translation.
- Argos's sentence-boundary-detector is itself backed by Stanza, whose default `Pipeline(...)` call unconditionally tries to fetch a resources index from `raw.githubusercontent.com` even when the package is already installed locally — this would silently reintroduce a network dependency at request time. `argos_translator.py` patches `StanzaSentencizer.lazy_pipeline` to use `stanza.DownloadMethod.REUSE_RESOURCES` instead, which reuses whatever `resources.json` is already cached under the installed package's own `stanza/` subdirectory. That cache is guaranteed to exist and be complete because `install_translation_models.py` runs one real `translate()` call per direction at build time (while the network is still available), not just `package.install_from_path()` — installing a package alone never touches Stanza's resources at all. Verified directly: `docker run --rm --network none <image> ...` translates correctly in both directions.
- Argos has no `pt-BR`/`pt-PT` distinction — just `pt`. Accepted as a known simplification, same spirit as this project's other documented approximations (e.g. EDAN's free-text dimensions in ADR-0001).
- `TranslatingProvider`'s existing try/except-and-fall-back-to-original-text resilience (both around query translation and `_translate_field`) is unchanged and stays as useful defense-in-depth — a corrupted or missing model file is still a real failure mode worth degrading gracefully from, even though a local engine has no network failure mode to guard against.

## Options Considered

### Stay on MyMemory, add persistent caching/batching

**Pros:** smallest possible change; no new dependency or image size growth.

**Cons:** mitigates the symptom, doesn't fix the cause — any sufficiently large batch of never-before-seen titles still exceeds the real 5 req/s ceiling regardless of how aggressively repeats are cached or batched. Rejected as a mitigation rather than a fix, which is exactly the distinction ADR-0001 itself drew when it named this as the trigger to revisit.

### A paid API (DeepL / Google Cloud Translation)

**Pros:** best quality and reliability, real SLA.

**Cons:** same objection ADR-0001 already raised against Option C there — requires account creation and secrets management the project doesn't have a story for yet. Doesn't remove network dependency either, just moves the reliability risk from "unofficial and rate-limited" to "official but still a runtime network call that can fail."

### Argos Translate, fully offline (chosen)

**Pros:** zero rate-limit risk by construction — there's no server to throttle it. No network dependency at request time at all, which also removes an entire class of production failure (DNS, TLS, upstream outage) that any network-backed translator carries regardless of who operates it.

**Cons:** a new native dependency (`argostranslate`, plus its own dependencies including `stanza`/CTranslate2); real Docker image size growth from bundled language models (~80MB per language-pair model, confirmed via image build); per-call cost shifts from network latency to local CPU inference (measured ~40ms/title once the model is warm). ADR-0001 rejected this option for V1 specifically because of the image-size cost against a "ship fast" constraint that no longer applies now that the project has a working Docker pipeline and this exact reliability problem has materialized.

## Consequences

- The running backend container never needs network access to translate — verified with `docker run --rm --network none`.
- Docker image size grows by roughly 80MB per language pair (2 pairs: `en→pt`, `pt→en`) plus the `argostranslate`/`stanza`/CTranslate2 dependency tree itself. Accepted as the direct cost of removing the rate-limit failure mode.
- `pt` instead of `pt-BR` is a known, accepted simplification — Argos Translate has no regional Portuguese variants.
- Per-call cost moves from network latency (and its associated rate-limit/outage risk) to local CPU inference. Under concurrent load this is bounded by CPU, not by an external service's throttle — a materially different (and here, better-understood) scaling characteristic.
- `backend/README.md` and `.claude/STEERING.md`'s "known risks" section, which documented MyMemory's no-SLA risk, need to be updated to reflect this change (tracked as a docs follow-up).
- Changing the language-pair set (e.g. adding a third language) requires rebuilding the Docker image so the new pair's models and warmed-up Stanza cache get baked in — this can't be done at runtime the way a network-backed translator's language list could be.
