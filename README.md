# DRL

Standalone Deep RL Lab web application and AIX sister project.

## Canonical Deploy

The canonical public DRL host is the standalone App Engine app in project
`deeprl-031026`:

- `https://deeprl-031026.wm.r.appspot.com`

Canonical deploy commands:

```bat
drl_cloud_configure.bat
drl_cloud_bootstrap.bat
drl_cloud_deploy.bat
```

Cloud Run remains available only as a legacy fallback path through
`drl_cloudrun_deploy.bat`.
