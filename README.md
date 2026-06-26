# DRL

Standalone Deep RL Lab web application.

## Canonical Publish

The canonical public DRL host is the Cloud Run service in project
`deeprl-031026`:

- `https://drl-web-x2ulcmhaiq-wm.a.run.app`

Normal publish command:

```bat
scripts\drl_cloudrun_publish.bat
```

Occasional support commands:

```bat
scripts\drl_cloud_status.bat
scripts\drl_cloud_configure.bat
scripts\drl_cloud_setup.bat
```

Low-cost appspot alias publish:

- `scripts\drl_appengine_publish.bat`
- `https://deeprl-031026.wm.r.appspot.com`

The appspot URL is an App Engine Standard F1 redirect alias. It is not the DRL
runtime.
