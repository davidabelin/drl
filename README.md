# DRL

Standalone Deep RL Lab web application.

## Canonical Publish

The canonical public DRL host is the standalone App Engine app in project
`deeprl-031026`:

- `https://deeprl-031026.wm.r.appspot.com`

Normal publish command:

```bat
scripts\drl_appengine_publish.bat
```

Occasional support commands:

```bat
scripts\drl_cloud_status.bat
scripts\drl_cloud_configure.bat
scripts\drl_legacy_cloud_setup.bat
```

Legacy fallback publish path:

- `scripts\drl_legacy_cloudrun_publish.bat`
