# **DONE WITH THIS** (3/22/2026)
# DRL Cloud Run Console Notes

Legacy note: Cloud Run is no longer the canonical public DRL host. The quick
deploy path now targets App Engine flexible so DRL has a cleaner standalone
Google-managed URL. Keep this document only for the fallback/legacy Cloud Run
path.

## Why this app is better on Cloud Run than App Engine standard

The DRL lab now includes:

- `gymnasium`
- `pygame-ce`
- `box2d-py`
- `torch`

That stack is much more comfortable in a containerized deploy path than in a lighter App Engine standard configuration. The repo now includes a production container in [Dockerfile](../Dockerfile) plus prefix-aware routing in [run.py](../run.py), so the same app can run:

- as a standalone service at `/`
- behind a path prefix such as `/drl`
- in local Flask development

## What is already wired in code

- `requirements.txt` defines the standalone runtime dependencies.
- `Dockerfile` builds a Cloud Run-ready container.
- `run.py` supports `APP_BASE_PATH` so the app can live at `/` or `/drl` without changing routes.
- `DRL_LUNAR_JOBS_ROOT` defaults to `/tmp/drl_lunar_jobs` in the container.

## Recommended first deploy shape

Use Cloud Run for the first standalone online DRL deployment.

Recommended initial environment variables:

- No cross-app back-link environment variable is used; DRL navigation should remain local.
- `APP_BASE_PATH`: leave empty for the standalone DRL service. Only set this to `/drl` when the service is actually being served behind that prefix.
- `DRL_LUNAR_JOBS_ROOT`: `/tmp/drl_lunar_jobs`
- `DRL_LUNAR_MAX_WORKERS`: `1`

## Important current Console detail

Google's current Cloud Run documentation distinguishes three practical paths:

1. Deploy an existing container image from Artifact Registry in the Cloud Run Console.
2. Connect a source repository for continuous deployment from the Cloud Run Console.
3. Deploy local source directly, which currently hands off to Cloud Shell and runs a `gcloud run deploy --source ...` flow.

That means a pure click-only upload of this local folder is not the normal current path. For your walkthrough, the cleanest options are:

- Cloud Shell from inside the Google Cloud Console
- a connected GitHub repo
- a container image pushed to Artifact Registry

## First walkthrough step

When you are ready, start in the Google Cloud Console with:

1. Create or select the new DRL project.
2. Verify billing is enabled for that project.
3. Enable these APIs:
   - Cloud Run Admin API
   - Cloud Build API
   - Artifact Registry API
   - Cloud Logging API

After that, we can decide whether you want the first deploy to use:

- Cloud Shell from the Console against this repo
- GitHub-connected source deployment
- Artifact Registry + Cloud Run image deployment
