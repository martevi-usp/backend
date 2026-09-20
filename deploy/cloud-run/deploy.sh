#!/usr/bin/env bash
# Deploys the backend to Google Cloud Run (backend ADR-0006).
#
#   GCP_PROJECT=my-project CORS_ORIGINS=https://my-frontend.workers.dev \
#     ./deploy/cloud-run/deploy.sh
#
# Optional: REGION (default us-central1), SERVICE (default martevi-backend),
# HARVARD_API_KEY, SMITHSONIAN_API_KEY.
set -euo pipefail

: "${GCP_PROJECT:?set GCP_PROJECT to your Google Cloud project id}"
: "${CORS_ORIGINS:?set CORS_ORIGINS to the frontend origin (comma-separated for several)}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-martevi-backend}"

# gcloud splits --set-env-vars on commas, and CORS_ORIGINS may contain some, so
# use a custom delimiter (^@^).
ENV_VARS="CORS_ORIGINS=${CORS_ORIGINS}"
[ -n "${HARVARD_API_KEY:-}" ] && ENV_VARS="${ENV_VARS}@HARVARD_API_KEY=${HARVARD_API_KEY}"
[ -n "${SMITHSONIAN_API_KEY:-}" ] && ENV_VARS="${ENV_VARS}@SMITHSONIAN_API_KEY=${SMITHSONIAN_API_KEY}"

# Build context is the backend repo root: the Dockerfile copies ./src and ./db.
cd "$(dirname "$0")/../.."

# 2 GiB: both translation models are ~800-930 MB resident on x86 (ADR-0006).
# max-instances 1 caps cost and keeps a single copy of the models in memory.
gcloud run deploy "$SERVICE" \
  --project "$GCP_PROJECT" \
  --region "$REGION" \
  --source . \
  --port 8000 \
  --memory 2Gi \
  --cpu 1 \
  --cpu-boost \
  --min-instances 0 \
  --max-instances 1 \
  --concurrency 20 \
  --timeout 300 \
  --allow-unauthenticated \
  --set-env-vars "^@^${ENV_VARS}"
