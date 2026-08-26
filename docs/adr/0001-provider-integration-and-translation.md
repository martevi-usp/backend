# ADR-0001: Museum Provider Integration & Translation Layer

**Status:** Proposed
**Date:** 2026-08-26
**Deciders:** martevi backend owner(s)

## Diagrams

- [**Architecture views** (4 pages: components · classes · modules · field/translation map)](https://lucid.app/lucidchart/e7fab22f-3485-4e45-92e4-9033a9948bcc/edit?invitationId=inv_339c5bbc-f062-4889-83b6-82fffbc09e1a)
- [**Sequence — artwork detail** (`GET /artworks/{id}`, translation on the way out)](https://lucid.app/lucidchart/6a7b4241-9e26-431e-8f8a-4ca476de51b3/edit?viewport_loc=-250%2C-432%2C3037%2C1427%2Cpage1&invitationId=inv_07925fd1-9c36-4eb8-a99b-69501f4606a4)
- [**Sequence — Museu Martevi / cross-museum search** (registry fan-out with a partial provider failure)](https://lucid.app/lucidchart/6a7b4241-9e26-431e-8f8a-4ca476de51b3/edit?viewport_loc=-824%2C-715%2C2543%2C1195%2CM7BopOs1J9x1&invitationId=inv_07925fd1-9c36-4eb8-a99b-69501f4606a4)

## Context

martevi aggregates artworks from multiple open museum collection APIs and renders each one at true physical scale. Two structural rules constrain this decision, not up for re-debate here: provider-specific code must stay behind a single boundary — swapping a provider should mean rewriting one normalizer and nothing else, never touching a router or a schema — and missing data must stay visible: a provider must never invent a dimension; a value it doesn't have must reach the frontend as `null`, not `0` or a dropped field.

The backend is currently an empty fastapi-gen scaffold (`GET/POST /items` stub, no real schema). No provider integration, no database, and no translation exist yet. Providers need to be wired up behind one interface, and — because the UI is pt-BR while every provider returns English-language metadata — that metadata needs to reach the frontend already translated, without leaking translation logic into each provider's normalizer or into the routers.

Constraints for this decision specifically: ship fast (no other infra — DB, deploy target — exists yet, and this shouldn't block on them), and stay free/cheap (no paid translation API). This revision also checks the design against the full product feature list (see **Requirement coverage** below) and extends the provider list with the best free-API candidates found.

## Decision

1. **Provider integration**: one shared `MuseumProvider` interface; one concrete Adapter class per museum that converts that museum's response shape into martevi's common `Artwork`/`ArtworkSummary` schema; a small registry (dict keyed by `provider_id`, built once at startup, injected via FastAPI `Depends`) that selects which provider(s) to call per request. Structurally this is the Adapter pattern (GoF) for the per-provider normalization, with a Strategy-shaped registry on top for runtime selection — see "Naming note" below on why "Strategy" alone undersells what's happening here.
2. **Translation**: a `TranslatingProvider` Decorator (GoF) that wraps any `MuseumProvider` — concrete or already-decorated — behind the *same* interface, translating only the free-text display fields (title, description, medium, culture/period label) after the wrapped provider returns. The registry wraps each provider at construction time (`PROVIDERS = {"met": TranslatingProvider(MetProvider(...), translator), ...}`), so callers never know translation happened.
3. **Schema surface**: `ArtworkSummary`/`Artwork` need fields for every field a screen actually renders, all `Optional` except identity fields — no field is invented if a provider doesn't have it:

    ```python
    class ArtworkSummary(BaseModel):
        id: str                       # "{provider_id}:{external_id}"
        provider_id: str
        title: str
        date: str | None              # translated where free-text
        thumbnail_url: str | None
        height_cm: float | None
        width_cm: float | None

    class Artwork(ArtworkSummary):
        description: str | None       # wall note / history — translated
        medium: str | None            # translated
        culture: str | None           # translated
        department: str | None        # section/department, only when the provider exposes one
        image_url: str | None         # highest-resolution image the provider offers
        image_zoom_url: str | None    # IIIF base URL / deep-zoom source, when the provider offers one
        source_url: str | None        # link back to the museum's own object page
    ```

    `department` and `image_zoom_url` are the two fields this revision adds to close gaps found in **Requirement coverage**. Both stay `Optional` and are populated per-adapter only when the underlying API actually has the data — consistent with the missing-data rule in Context.

4. **Fan-out tolerance**: any view that queries every provider at once (the "martevi museum" — see coverage below) calls the registry with `asyncio.gather(..., return_exceptions=True)` and returns partial results plus a per-provider status, rather than failing the whole request when one provider (most likely Smithsonian, given its `DEMO_KEY` throttle) times out or errors.

### Naming note: Strategy vs. Adapter

Both names are right about different halves of the same object:

- **Adapter** describes *why* `MetProvider`/`HarvardProvider`/etc. exist: each converts an incompatible external interface (Met's JSON shape, EDAN's free-text dimensions, Harvard's field names) into one interface martevi already expects. That's the per-provider normalizer.
- **Strategy** describes *how the registry picks one*: interchangeable implementations of the same operation (`search`, `get_item`), selected at runtime by `provider_id`. That's the registry/DI layer.

In Python the code shape ends up identical either way (interface + concrete classes + a dict-based dispatcher), so this isn't a rewrite decision — it's a vocabulary one. This ADR uses "Adapter" for the per-provider classes and reserves "Strategy" for describing the registry's runtime dispatch, so the two names don't collide when read side by side.

## Provider list

### Original five

Met, Art Institute of Chicago, Harvard Art Museums, Rijksmuseum, Smithsonian Open Access (EDAN).

### Recommended additions

- **Cleveland Museum of Art Open Access API** — free, no key, CC0. Returns dimensions already in meters and 60+ structured fields (title, description variants, provenance, technique). The cleanest possible 7th adapter: no auth friction, no free-text dimension parsing to fight with.
- **Victoria and Albert Museum API** — free, decorative arts/design collection, records object dimensions. Good breadth complement to the existing five (painting-heavy) collections.

Both fit the `MuseumProvider` interface with no design changes — they're exactly what Option A (Adapter classes + registry) was built to absorb cheaply.

### Considered, not recommended yet

- **Statens Museum for Kunst (SMK), Denmark** — likely free/no-key, CC0, has dimensions. Held back for one reason: its metadata is primarily Danish, not English. The `TranslatingProvider` decorator as designed assumes an English source language flowing into the `Translator`; a Danish-source provider either needs a translator backend with source-language auto-detection (most, including `deep-translator`, support this) or an explicit `source_lang` per provider. Worth a follow-up spike, not a blocker, but not free to add today.
- **Europeana** — aggregates thousands of European institutions behind one API, free but requires a signup API key, and per-item data quality (especially dimensions) varies by the original contributing institution. This doesn't fit the "one Adapter = one museum" model cleanly — it's closer to a meta-provider that would need its own normalization strategy per source institution. Worth considering later as a way to add breadth without N individual adapters, but it's a different shape of decision than this ADR makes.
- **Wikidata / Wikimedia Commons structured data** — fully free, no key, enormous coverage via SPARQL. Same caveat as Europeana on a smaller, crowd-sourced scale: dimension data isn't guaranteed present or consistently formatted, similar to the free-text problem already known from EDAN.
- **DPLA** — the US equivalent of Europeana; same aggregator caveats.

### Ruled out

- **Google Arts & Culture** — no public developer API; embed/iframe only, not usable for a real backend integration.
- **Artsy** — API access is gated behind partner approval, not open-access in the CC0 sense the rest of this collection relies on.

## Options Considered

### Provider integration

#### Option A: Adapter classes + DI registry (chosen)

| Dimension        | Assessment                                                                           |
|------------------|--------------------------------------------------------------------------------------|
| Complexity       | Low — one interface, one small class per museum, one dict                            |
| Cost             | None                                                                                 |
| Scalability      | Confirmed cheap up to 7 providers (see Provider list); each addition is one new file |
| Team familiarity | High — plain OOP, no new dependency                                                  |

**Pros:** trivial to unit-test each adapter in isolation against recorded fixtures; `asyncio.gather` across the registry's values gives "search every museum at once" (the martevi-wide view) with no extra architecture, just a fan-out call plus the partial-failure handling in Decision #4.

**Cons:** none specific to this option at current scale.

#### Option B: Plugin/entry-points loading (`importlib.metadata`)

| Dimension | Assessment |
| --- | --- |
| Complexity | Medium-high — needs packaging metadata, discovery logic |
| Cost | None |
| Scalability | Better only if third parties ship provider plugins independently |
| Team familiarity | Low |

**Pros:** providers could be installed/removed without touching martevi's own source.

**Cons:** solves a problem martevi doesn't have — the provider list is a fixed, curated set (only museums that publish an open API, chosen by the team, not user-installable). Adds indirection for zero present benefit.

#### Option C: One big `if provider == ...` dispatcher, no interface

**Pros:** fastest possible to type today.

**Cons:** directly violates the single-boundary rule from Context — provider-specific branching would leak into whatever calls it, the exact failure mode this project explicitly avoids. Rejected outright, included only for completeness.

### Translation

#### Option A: `deep-translator` (Google backend, free, no key) wrapped in a Decorator — chosen for V1

| Dimension        | Assessment                                                      |
|------------------|-----------------------------------------------------------------|
| Complexity       | Low — one dependency, ~15 lines                                 |
| Cost             | Free                                                            |
| Scalability      | Unofficial endpoint — rate-limited/blockable under real traffic |
| Team familiarity | N/A, trivial API                                                |

**Pros:** zero signup, zero secrets to manage, fastest to ship, satisfies both stated constraints (free + fast); the Decorator boundary means swapping the backend later touches only the `Translator` implementation, nothing in the providers or routers. Also supports source-language auto-detection, which matters if SMK (Danish-source) gets added later.

**Cons:** unofficial/reverse-engineered Google endpoint — no SLA, can break or get IP-throttled if traffic grows. Accepted as a known, short-term risk.

#### Option B: LibreTranslate (public instance or self-hosted)

**Pros:** open-source, official-ish API contract, self-hostable for full control.

**Cons:** public instance shares the same "free but unreliable/rate-limited" profile as Option A without the "already just works" advantage; self-hosting means a new Docker service plus downloading translation models — real infra weight that cuts against the "ship fast" constraint given no DB/deploy infra exists yet either.

#### Option C: DeepL or Google Cloud Translation (official, paid-tier-but-free-quota)

**Pros:** best quality and reliability, real SLA, generous free quota (DeepL: 500k chars/month).

**Cons:** requires account creation and a secret key at minimum (Google Cloud's free tier still requires a billing account on file); adds secrets management the project doesn't have a story for yet. Good candidate for V2 once traffic/quality pressure justifies the setup cost — the Decorator makes that swap a one-file change, not a redesign.

#### Option D: Argos Translate (fully offline)

**Pros:** no network dependency, no rate limits, no external ToS risk.

**Cons:** needs roughly 1-2 GB of model files bundled into the backend Docker image per language pair — conflicts with the existing lean dev/production image split and with "ship fast" now. Worth revisiting only if network-dependent translation becomes a reliability problem sin production.

## Requirement coverage

Checked against the current product feature list. "Covered" means this ADR's design already handles it; "covered via schema addition" points at the `department`/`image_zoom_url` fields added in this revision; a few items are explicitly not this ADR's problem.

| Feature | Status |
| --- | --- |
| Ver quadros em escala (relativa ao usuário) | Covered — `height_cm`/`width_cm` on `Artwork`, `Optional`, never fabricated |
| Explorar o quadro: zoom | Covered via schema addition — `image_url` (highest-res available) plus `image_zoom_url` for providers that expose IIIF or another deep-zoom source. Actually wiring a deep-zoom viewer is frontend; picking the best available image per provider is the adapter's job |
| Conteúdo: imagem, título, data, história | Covered — `title`, `date`, `description`, `image_url` on the schema above |
| Divisão por museu e subdivisão por seções/departamentos | Covered via schema addition — `department`, `Optional`, populated only "conforme API disponibiliza" per your own phrasing; browsing by department is a router-level filter on top of this field, not a new pattern |
| "Museu Martevi" com todas as obras | Covered — this is exactly the registry's fan-out (`asyncio.gather` across every provider), with the partial-failure handling added in Decision #4 so one throttled provider (Smithsonian) doesn't take the whole view down |
| Links para tour virtuais | Explicitly out of scope for this ADR — this is static/curated data (museum → tour URL), not provider-API data, and doesn't touch the `MuseumProvider` interface at all. Simplest path: a small config/table once the database lands; doesn't need an adapter |
| Busca por nome do quadro | Covered — this is exactly `MuseumProvider.search(query, limit)`; the martevi-wide search is the same fan-out as "Museu Martevi" |

Net: three schema fields (`department`, `image_zoom_url`) and one behavioral rule (fan-out tolerates partial provider failure) were the actual gaps; everything else was already implied by the original design or is legitimately outside it.

## Trade-off Analysis

The two decisions are coupled through one interface, which is the point: `MuseumProvider` is the contract both the Adapter classes and the `TranslatingProvider` decorator implement, so translation is opt-in per provider without changing the provider or the router. The real trade-off isn't between the two patterns (both are cheap, well-understood, and match the constraints in Context) — it's between shipping the unofficial free translation backend now versus the reliability of a paid one. Given the explicit constraints (free/cheap, short timeline), Option A for translation is the right call *for now*, provided it's tracked as a known risk, not silently assumed permanent.

One constraint that must hold regardless of translation backend: only free-text display fields get translated. Dimensions, dates as raw values, and IDs pass through untouched — translating a numeric or structured field, or silently dropping a `null` dimension instead of passing it through, would violate the missing-data rule in Context. This should be enforced by the `TranslatingProvider`'s field allowlist, not by convention.

## Consequences

- Adding a new provider (Cleveland, V&A, or otherwise) means one new Adapter class plus one registry entry — no change to routers, schemas, or the translation layer.
- Swapping the translation backend later (LibreTranslate, DeepL, Google Cloud) means changing the `Translator` implementation injected into `TranslatingProvider` — zero changes to provider adapters or callers.
- A non-English-source provider (SMK) needs the `Translator` to support per-call source-language detection or configuration before it can be added — not a redesign, but not zero-cost either.
- Translating on every request re-translates the same artwork metadata repeatedly, which is both wasteful and the fastest way to hit the free backend's rate limit. This ADR doesn't decide caching (out of scope, and caching/DB infra is already deferred project-wide) — but it's the natural next follow-up, and should land before real traffic, not after the free backend starts failing.
- `deep-translator`'s Google backend is an unofficial dependency accepted as a short-term risk, in the same category as the Smithsonian `DEMO_KEY` throttle (~30 req/hr) that already constrains that provider — and now also constrains how aggressively the "Museu Martevi" fan-out can hit it.
- `image_zoom_url` will be populated for some providers (e.g. Harvard and Rijksmuseum both expose IIIF) and not others — the frontend's zoom viewer needs a fallback path (plain high-res `image_url` with client-side pan/zoom) for providers without a deep-zoom source. That viewer choice is a frontend decision, not this one.
- `Protocol` vs. `ABC` for `MuseumProvider` is left as an implementation detail, not a decision this ADR makes — either satisfies the interface requirement; pick whichever the first adapter's PR reviewer prefers and stay consistent.
