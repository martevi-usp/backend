# ADR-0006: Deployment Target — Cloud Run for the Backend, Static Assets for the Frontend

**Status:** Proposed
**Date:** 2026-09-20
**Deciders:** martevi backend owner(s)

## Context

The course brief requires a running application at a reachable URL by 2026-12-01, and the project should cost nothing to run. No deploy target existed; Docker images built and went nowhere.

The backend constrains the choice: a long-lived process, concurrent multi-provider fan-out with SSE (ADR-0003), and an in-process native translation model (ADR-0002, ADR-0005) that needs `ctranslate2`. It is not a serverless-function workload.

## Decision

- **Backend:** Google Cloud Run, from the existing `production` Docker image, built from the Dockerfile's last stage by `gcloud run deploy --source`. 2 GiB, 1 vCPU, startup CPU boost, `min-instances 0`, `max-instances 1`, concurrency 20. `deploy/cloud-run/deploy.sh` wraps the command.
- **Frontend:** Cloudflare Workers static assets (`frontend/wrangler.jsonc`), built with `VITE_API_URL` set to the Cloud Run URL. Requests to static assets are free and unlimited on Cloudflare's free plan. (Cloudflare Pages is in maintenance; Workers static assets is the current path.)
- **No external database service** (ADR-0004).
- **`GET /health`** exists and stays free of provider, database and model access (`api/health.py`, with a test that runs it without any of them). It is `/health`, not `/healthz`: Cloud Run's Google front end answers `/healthz` itself with a 404 before the request reaches the container (seen on the first deploy), which would also stop the warm-up ping from waking the instance. The frontend fires a warm-up ping once per page load from `App.tsx`, on every route, ignoring failures; the placeholder home page is where a first-time visitor waits while the backend wakes.
- `CORS_ORIGINS` and the optional museum API keys are passed as environment variables.

## History: how this decision was reached

1. **Render free plan (first choice).** Docker runtime on the free tier, `production` as the last Dockerfile stage (Render builds the last stage and has no `--target`). Free instances spin down after 15 idle minutes and take about a minute to wake, and free hours are capped at 750 a month per workspace, so a 24/7 keep-alive would consume the whole allowance. This choice assumed Argos Translate fits in 512 MB.
2. **Memory gate, run against that assumption (fails).** On the linux/amd64 `production` image, a container capped at 512 MB was OOM-killed on the first Portuguese cross-museum search. Resident memory: 98 MB after import, +358 MB when the en→pt model loads, +350 MB when pt→en loads, about 800 MB with both loaded and 930 MB after real searches. The same script measured 333 MB on native arm64. CTranslate2 alone loads one en→pt model at +308 MB in `int8` and +568 MB in `float32` on x86; forcing the CPU path (GENERIC, AVX, AVX2), `int8_float32` or a single thread left the total at 791 to 806 MB. Two mitigations were tried: sharing the translators (already one per direction) and serialising each model's first load, which cut a burst peak of 2 GB to about 930 MB but does not get under 512 MB. A free 512 MB x86 instance is ruled out; the backend needs at least 1 GiB.
3. **Cloudflare Containers (evaluated, working config written, rejected).** `standard-1` (4 GiB, 1/2 vCPU) fits and gives one provider for everything, and the config passed `wrangler deploy --dry-run`. It requires the $5/month Workers Paid plan; there is no free tier for Containers.
4. **Free options researched against current documentation.** Hugging Face Docker Spaces now require a paid plan to create. Koyeb's pricing lists no free compute plan. Oracle Cloud Always Free (ARM) fits the models but means running a VM, and idle Always Free instances can be reclaimed. Google Cloud Run's Always Free tier fits.
5. **Cloud Run chosen.** Verified locally on the amd64 image capped at 2 GiB and 1 CPU: peak 938 MB under concurrent searches, no OOM.

## Why Cloud Run fits the free tier

The Always Free tier is 2 million requests, 360,000 GiB-seconds of memory and 180,000 vCPU-seconds a month. With request-based billing an instance is charged only while it processes requests and while it starts or shuts down, and it stops after at most 15 idle minutes. At 2 GiB and 1 vCPU that is about 50 hours of active time a month; a 20-second search uses about 40 GiB-seconds and 20 vCPU-seconds, so on the order of 9,000 searches a month stay free. Idle time costs nothing.

## Options Considered

- **Render free (512 MB).** Ruled out by the memory measurement (History, step 2).
- **Render or another host on a paid x86 plan.** Works; costs money each month.
- **Cloudflare Containers.** Rejected as above: paid plan required.
- **Hugging Face Docker Spaces, Koyeb.** Rejected: no free compute.
- **Oracle Cloud Always Free (ARM).** Free and the models fit (333 MB), but it is a VM to run and patch, and an idle demo is exactly what Oracle may reclaim.
- **Vercel for the backend.** Serverless keeps no process between requests, execution limits are likely exceeded by fan-out and SSE, and it cannot carry the model.
- **Cloudflare Workers / Python Workers.** Ruled out on runtime, not size: they run under Pyodide in V8 isolates and `ctranslate2` cannot load there.
- **Hosted database on Render / Neon / D1.** See ADR-0004.
- **Pre-translate at seed time.** Removes the model, the image weight and the memory problem, and fits any free tier, but does not cover free-text search returning uncurated works. **This remains the fallback** if Cloud Run's free tier stops being viable.

## Consequences

- **A billing account with a card is required** even for the free tier ("A Google Cloud billing account is required to access the Google Cloud Free Tier"). Charges apply only beyond the quotas; `max-instances 1` caps runaway scale and a budget alert should be set. The card requirement is the price of "free".
- **Latency.** One vCPU is slow for translation. Measured locally on the amd64 image capped at 2 GiB and 1 CPU (under Rosetta, with real provider network time): a cross-museum search took 19 to 24 seconds. `--cpu 2` would roughly halve compute time but halve the free active hours too.
- **Cold start.** The first request after idle waits for the container start and the first model load; startup CPU boost is enabled, and the warm-up ping hides part of it. Not measured on Cloud Run.
- **Single instance.** No redundancy; concurrent requests share one process and one copy of the models. Concurrency 20 is not tuned.
- **Unverified until the first deploy:** whether the free quota applies to the chosen region (`us-central1` assumed), whether the roughly 1.2 GB image in Artifact Registry stays within the free storage allowance, SSE behaviour, and real cold-start and latency figures.
- Deploying needs the owner's Google account and `gcloud` login; the steps are in `deploy/cloud-run/README.md`. Continuous deployment is described there too.
