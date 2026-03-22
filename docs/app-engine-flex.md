# DRL App Engine Flexible Deploy

Canonical standalone DRL deploy now targets App Engine flexible in project
`deeprl-031026`.

## Status check (2026-03-22)

- [x] App Engine flexible config is present in `app.yaml`
- [x] The container runtime remains the source of truth via `Dockerfile`
- [x] `requirements.appengine.txt` pins the CPU-only PyTorch wheel
- [x] The canonical public host is `https://deeprl-031026.wm.r.appspot.com`
- [x] The normal App Engine publish script and legacy support scripts are present under `scripts/`
- [ ] Live Lunar sessions are fully production-ready on App Engine without additional verification

## Runtime shape

- `app.yaml` uses `runtime: custom` and `env: flex`
- `app.yaml` now also enables `session_affinity`, pins the service to one instance, and requests `2 vCPU / 2.3 GB` so the live Lunar session flow behaves more like the earlier single-instance Cloud Run setup
- `Dockerfile` remains the source of truth for the container runtime
- `requirements.appengine.txt` pins the CPU-only PyTorch wheel so App Engine
  does not pull the much larger CUDA stack during image builds
- `AIX_HUB_URL` points back to `https://aix-labs.uw.r.appspot.com/`
- `APP_BASE_PATH` stays unset for the standalone host

## Normal path

```bat
scripts\drl_appengine_publish.bat
```

## Occasional support

```bat
scripts\drl_cloud_status.bat
scripts\drl_cloud_configure.bat
scripts\drl_legacy_cloud_setup.bat
```

## Expected public host

- `https://deeprl-031026.wm.r.appspot.com`

If the project already has an App Engine app in a different region, use the
actual `defaultHostname` returned by `gcloud app describe`.
