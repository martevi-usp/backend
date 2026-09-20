# ADR-0005: Install Argos Translate Without `torch`

**Status:** Proposed
**Date:** 2026-09-20
**Deciders:** martevi backend owner(s)
**Amends:** ADR-0002 (its Stanza sentence-splitter patch and warm-up are obsolete — see below)

## Context

ADR-0002 chose Argos Translate for offline translation and accepted "real Docker image size growth". The current `Dockerfile` installs it with a plain `pip install argostranslate>=1.11`. That pulls `stanza==1.10.1`, which pulls `torch`, whose Linux wheels bundle the CUDA stack. Measured in a clean Linux venv, the install exhausted disk at **4.1 GB** of site-packages (2.8 GB `nvidia/`, 897 MB `triton/`). `ARGOS_DEVICE_TYPE=cpu` selects where inference runs; it does not stop pip downloading CUDA wheels. That image cannot run on a small free host (ADR-0006).

ADR-0002 also assumed Stanza is Argos's sentence-boundary detector, and patched it to stay offline. Argos 1.11.0 treats Stanza as legacy (`ARGOS_STANZA_AVAILABLE` is commented out in `settings.py`) and defaults to MiniSBD, but the choice is made **per model package**: `translate.py` picks `StanzaSentencizer` whenever the package embeds a Stanza tokenizer, and the published en/pt packages do (verified: without the setting below, the build fails with `module 'stanza' has no attribute 'Pipeline'`). Separately, `sbd.py` does an unguarded module-level `import stanza`, so the package cannot be imported without it, a packaging defect upstream.

## Decision

1. `pip install --no-deps argostranslate==1.11.0` (pinned).
2. Install its real runtime deps explicitly (declared in `pyproject.toml`): `ctranslate2`, `sentencepiece`, `sacremoses`, `minisbd`, `packaging`.
3. Provide a stub `stanza` package whose only job is to satisfy the import.
4. Set `ARGOS_CHUNK_TYPE=MINISBD` so Argos never selects the Stanza sentencizer, regardless of what the model packages embed.
5. Set `XDG_DATA_HOME=/opt/argos-translate/data` so MiniSBD's lazily downloaded model, fetched by the build-time warm-up translation, lands where the non-root runtime user can read it (otherwise it sits in root's home and is re-downloaded at request time).
6. Delete the Stanza `lazy_pipeline` patch from `argos_translator.py`; the warm-up in `install_translation_models.py` stays, now warming MiniSBD.
7. No `build-essential`: every dependency has a `cp314` wheel and the `production` image builds without a compiler.

Measured in the built image (linux/arm64, Docker Desktop): site-packages **326 MB** and no torch/nvidia packages, against 4.1 GB+; translation en→pt and pt→en works under `docker run --network none`; peak RSS of a bare Python process holding both models is **334 MB**.

## Options Considered

- **Full dependency tree** — simple, but 4.1 GB; rejected.
- **CPU-only torch index** — shrinks torch to ~200 MB yet still ships a framework nothing calls; `--no-deps` is smaller.
- **Remote translation API** — reintroduces the rate-limit/network failure ADR-0002 removed.
- **Pre-translate at seed time** — would remove the model entirely, but cannot cover free-text search over uncurated works. Kept as the fallback in ADR-0006.

## Consequences

- **Accepted risk:** pip resolves nothing. The version stays pinned; the block must be reviewed on every argostranslate bump, and the stub breaks loudly if MiniSBD ever stops being default.
- **Memory depends on the CPU architecture.** The 334 MB figure above is arm64. On linux/amd64 (what hosts run) the same two models are about 800 MB resident and 930 MB after real searches, because CTranslate2's x86 backend loads each model at about 308 MB in `int8`. That rules out 512 MB hosts; see ADR-0006 for the measurements and the resulting deployment choice.
- **Concurrent first calls used to load a model several times.** Argos builds each language pair's model lazily with no lock, so a fan-out burst peaked near 2 GB. `ArgosTranslator` now serialises only the first call per pair (`_translate_blocking`); later calls run concurrently.
