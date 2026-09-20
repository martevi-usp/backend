# Cloud Run deploy (backend)

The backend's `production` Docker image, built by Cloud Build and run on
Google Cloud Run. Why Cloud Run and why these limits: see
`docs/adr/0006-deploy-cloud-run-and-static-frontend.md`.

## Before the first deploy

1. A Google Cloud project with a **billing account attached**. Google
   requires one even for the Always Free tier; you are only charged beyond
   the free quotas.
2. The `gcloud` CLI, then `gcloud auth login`.
3. Enable the APIs once:

   ```bash
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
     artifactregistry.googleapis.com --project <your-project>
   ```

4. Let Cloud Build use the source you upload. In newer projects the build
   runs as the default compute service account, which by default cannot read
   the source bucket, and the first deploy fails with `does not have
   storage.objects.get access`. Grant it the builder role (find the number
   with `gcloud projects describe <project> --format 'value(projectNumber)'`):

   ```bash
   gcloud projects add-iam-policy-binding <project> \
     --member "serviceAccount:<project-number>-compute@developer.gserviceaccount.com" \
     --role roles/cloudbuild.builds.builder
   ```

   Wait about a minute for it to take effect. This role is Google's usual fix
   for that error; if a deploy still fails on a permission, the message
   names what is missing.
5. Set a **budget alert** (Billing > Budgets & alerts), for example at a few
   dollars, so an unexpected charge doesn't go unnoticed.

## Deploy

```bash
GCP_PROJECT=<your-project> \
CORS_ORIGINS=https://<your-frontend>.workers.dev \
  ./deploy/cloud-run/deploy.sh
```

The first run needs the frontend's URL for `CORS_ORIGINS`. If you don't have
it yet, deploy with a placeholder, deploy the frontend using the backend URL
that gcloud prints (see the frontend README), then run this again with the
real origin.

Optional museum keys: export `HARVARD_API_KEY` and/or `SMITHSONIAN_API_KEY`
before running the script. They are stored as plain environment variables on
the service; use Secret Manager instead if that matters to you.

## Check it

```bash
curl https://<service-url>/health
curl https://<service-url>/puzzles | head -c 200
```

The first request after idle is slower: the instance has to start and load
the translation models on the first search.

## Tear down

```bash
gcloud run services delete martevi-backend --region us-central1 --project <your-project>
```

The built image stays in Artifact Registry (repository
`cloud-run-source-deploy`) until you delete it.

## Continuous deployment

`.github/workflows/deploy.yml` deploys to Cloud Run whenever backend CI
passes on `main` (and on demand from the Actions tab). It runs the same
`deploy.sh`, then checks `/health`.

It authenticates with Workload Identity Federation, so no Google key is
stored in GitHub. One-time setup (replace `PROJECT` and `PROJECT_NUMBER`;
the repository below is the backend's GitHub repository):

```bash
P=PROJECT
NUM=PROJECT_NUMBER   # digits only, e.g. 56935232287 — no "projects/" prefix
REPO=martevi-usp/backend

gcloud iam workload-identity-pools create github --project $P --location global
gcloud iam workload-identity-pools providers create-oidc github \
  --project $P --location global --workload-identity-pool github \
  --issuer-uri https://token.actions.githubusercontent.com \
  --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition "assertion.repository=='$REPO'"

gcloud iam service-accounts create martevi-deployer --project $P
SA=martevi-deployer@$P.iam.gserviceaccount.com
gcloud iam service-accounts add-iam-policy-binding $SA --project $P \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/$NUM/locations/global/workloadIdentityPools/github/attribute.repository/$REPO"
```

Give that service account (the one GitHub deploys as, not the compute account above) the roles `gcloud run deploy --source` needs:
`roles/run.admin`, `roles/cloudbuild.builds.editor`,
`roles/artifactregistry.writer`, `roles/storage.admin` (for the source
upload bucket) and `roles/iam.serviceAccountUser` on the project's default
compute service account. This list is from memory and not verified; if a
deploy fails on permissions, the error names the missing role.

Then in the backend GitHub repository (Settings > Secrets and variables >
Actions), create an environment named `production` and set:

| Kind | Name | Value |
|---|---|---|
| Variable | `GCP_PROJECT` | your project id |
| Variable | `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github/providers/github` |
| Variable | `GCP_SERVICE_ACCOUNT` | `martevi-deployer@PROJECT.iam.gserviceaccount.com` |
| Variable | `CORS_ORIGINS` | the frontend's origin |
| Variable (optional) | `GCP_REGION` | defaults to `us-central1` |
| Secret (optional) | `HARVARD_API_KEY`, `SMITHSONIAN_API_KEY` | your keys |

To require a manual approval before each deploy, add required reviewers to
the `production` environment.

The workflow has not been run: it needs your Google project and GitHub
settings, and none of it can be exercised from a local checkout.
