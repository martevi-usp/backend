# ADR-0003: Streaming Fan-Out Search over SSE

**Status:** Accepted
**Date:** 2026-09-13
**Deciders:** martevi backend owner(s)

## Context

ADR-0001 established fan-out search (`fan_out_search`, `asyncio.gather(..., return_exceptions=True)` across every registered provider) and its partial-failure tolerance, but never addressed *response delivery*: `GET /artworks` with no `provider_id` blocks on the slowest of up to 7 providers before returning anything, even when most providers already have results ready. A provider that's merely slow (not failing) still delays every other provider's results from reaching the client — the exact same "one provider degrades the whole request" shape the partial-failure handling in ADR-0001 was built to avoid for *failures*, just not yet addressed for *latency*.

This became a concrete UX problem once the frontend's dedicated cross-museum search page (`/busca`) started driving real fan-out traffic: a broad query against all 7 providers waits on whichever museum's API is slowest that request, even though most results are typically ready well before that.

## Decision

Add a streaming variant of fan-out search, delivered over **Server-Sent Events (SSE)**, alongside the existing non-streaming endpoint (kept, not replaced):

- `stream_fan_out_search(providers, query, limit)` (`backend/src/martevi/providers/fanout.py`) — an async generator that starts one task per provider and yields each provider's `(ProviderSearchStatus, list[ArtworkSummary])` outcome as soon as that task completes, in **completion order**, not registry order. Implemented with an explicit `asyncio.Queue` fed by per-task `add_done_callback`s rather than `asyncio.as_completed`: `as_completed` wraps each awaitable in a new internal future and yields those wrappers, not the original task objects, which makes it unusable for recovering *which provider* just finished from a dict keyed by the original tasks — confirmed directly (a dict lookup keyed on the yielded object raises `KeyError` since it's never the same object as the original task).
- `GET /artworks/stream` (`backend/src/martevi/api/artworks.py`) — `q` required, no `provider_id` (fan-out only; museum-scoped search and browse are already single fast requests and don't need this). Returns a `StreamingResponse` with `media_type="text/event-stream"`: one `event: provider` frame per provider outcome as it arrives, then a trailing `event: done` frame once the generator is exhausted, so the client can distinguish "no more providers coming" from "still waiting" rather than inferring it from silence or a timeout.
- The existing `GET /artworks` fan-out path (`fan_out_search`, unchanged) stays in place — it's simple, already tested, documented, and a non-browser client may still want one plain JSON response rather than an event stream.
- On the frontend, only `/busca` (cross-museum search) adopts the streaming endpoint (`streamFanOutSearch()` in `src/api/client.ts`, via the browser's native `EventSource`). Museum-scoped search and browse mode are untouched — still the plain REST endpoint via `searchArtworks`/`browseArtworks`.

## Options Considered

### SSE (chosen)

**Pros:** one-directional (server→client) and request-scoped, which is exactly the shape of this problem — the client never needs to push anything back after the initial query. Native browser support via `EventSource` (no client library needed); plain HTTP, so it works through the same infra (proxies, CORS) already handling every other endpoint; trivial to keep the non-streaming endpoint alongside it since both are just different response types over the same underlying `stream_fan_out_search`/`fan_out_search` split.

**Cons:** one-directional by design — would need replacing if a future feature actually needed the client to send data over the same connection after the initial request (not a need this feature has).

### WebSockets

**Pros:** bidirectional, if that were ever needed.

**Cons:** adds real complexity — connection lifecycle (reconnect logic, ping/pong keepalives), a bidirectional framing protocol — for a case that never needs the client to push anything after the initial query. Rejected as solving a problem (bidirectional communication) this feature doesn't have, at a real implementation and operational cost (a WebSocket-aware proxy/load-balancer story) the project doesn't need to take on yet.

### Polling (client re-requests `/artworks` on an interval)

**Pros:** no new backend endpoint or client API at all.

**Cons:** doesn't actually solve the problem — each poll would still be a full fan-out request blocking on the slowest provider; the only way to make partial progress visible would be duplicating fan-out's partial-completion logic into a client-side polling loop, which is strictly worse than doing it once, correctly, on the server. Rejected outright.

## Consequences

- Results from fast providers now reach the client well before slow or failing ones finish — confirmed via a test with an artificially slow provider (`test_stream_a_slow_failing_provider_does_not_block_a_fast_one`) that a fast provider's event arrives before a slower, failing one's.
- Two fan-out code paths now exist (`fan_out_search`, `stream_fan_out_search`) sharing no code beyond both depending on `MuseumProvider.search`; a future change to fan-out orchestration (e.g. a new partial-failure policy) needs to be applied to both, not just one.
- The frontend's masonry grouping (`withGroupLabels`, `masonry.ts`) relies on each provider's results arriving as one contiguous run to place a museum label before it — streaming preserves this because each SSE `provider` event carries that provider's *entire* result batch in one frame, never split across multiple events.
- Re-triggering a fan-out search mid-session (e.g. the user loads more results, which re-issues a fresh request with a larger `limit`) opens a new SSE connection from scratch rather than resuming the previous one — results visibly rebuild from empty as each provider responds again, rather than the previous single-swap behavior of the non-streaming path. This is an accepted, inherent trade-off of "progressively reveal as providers respond," not a regression specific to the load-more case.
- Only `/busca` streams; if a future screen needs cross-museum search with progressive loading, it should reuse `streamFanOutSearch` rather than growing a second streaming client.
