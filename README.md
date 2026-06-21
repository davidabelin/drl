# DRL

Standalone Deep RL Lab web application.

## Canonical Publish

The canonical public DRL host is the Cloud Run service in project
`deeprl-031026`:

- `https://drl-web-x2ulcmhaiq-wm.a.run.app`

Normal publish command:

```bat
scripts\drl_legacy_cloudrun_publish.bat
```

Occasional support commands:

```bat
scripts\drl_cloud_status.bat
scripts\drl_cloud_configure.bat
scripts\drl_legacy_cloud_setup.bat
```

Legacy compatibility alias publish:

- `scripts\drl_appengine_publish.bat`
- `https://deeprl-031026.wm.r.appspot.com`
