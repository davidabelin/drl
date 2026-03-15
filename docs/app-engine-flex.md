# DRL App Engine Flexible Deploy

Canonical standalone DRL deploy now targets App Engine flexible in project
`deeprl-031026`.

## Runtime shape

- `app.yaml` uses `runtime: custom` and `env: flex`
- `Dockerfile` remains the source of truth for the container runtime
- `requirements.appengine.txt` pins the CPU-only PyTorch wheel so App Engine
  does not pull the much larger CUDA stack during image builds
- `AIX_HUB_URL` points back to `https://aix-labs.uw.r.appspot.com/`
- `APP_BASE_PATH` stays unset for the standalone host

## Quick path

```bat
drl_cloud_configure.bat
drl_cloud_bootstrap.bat
drl_cloud_deploy.bat
```

## Expected public host

- `https://deeprl-031026.wm.r.appspot.com`

If the project already has an App Engine app in a different region, use the
actual `defaultHostname` returned by `gcloud app describe`.
