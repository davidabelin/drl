# DRL App Engine Standard Alias

Cloud Run is the DRL runtime. The App Engine appspot URL is kept only as a
low-cost App Engine Standard redirect alias:

- Runtime URL: `https://drl-web-x2ulcmhaiq-wm.a.run.app/`
- Appspot alias: `https://deeprl-031026.wm.r.appspot.com/`

## Current Shape

- `appengine_redirect/app.yaml` uses App Engine Standard `python313`, `F1`, and
  `max_instances: 1`.
- `appengine_redirect/main.py` redirects all paths to the Cloud Run service with
  HTTP 308.
- `scripts/drl_appengine_publish.bat` deploys only this Standard alias.
- There is no root App Engine runtime manifest in the repo.

## Rules

- Do not add a root `app.yaml` for DRL.
- Keep App Engine files under `appengine_redirect/` unless DRL is explicitly
  reimplemented for App Engine Standard later.
- Do not add a second App Engine requirements file or deploy script.
- If the appspot alias is no longer useful, delete the alias service instead of
  replacing the Cloud Run runtime.
