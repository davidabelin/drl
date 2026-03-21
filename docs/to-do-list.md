# DRL Running List of Changes To Make

Status refresh: 2026-03-17

## Legacy URL: `https://drl-web-x2ulcmhaiq-wm.a.run.app/`
- [x] Replace the ugly generated DRL URL as the canonical entry point.
  - Current canonical DRL URL is `https://deeprl-031026.wm.r.appspot.com/`
  - AIX already points to the canonical App Engine URL, and that canonical URL serves the updated chrome
- [x] Change `Back to AIX Hub` to `AIX Labs` and point it to AIX.
  - Verified on the canonical App Engine DRL URL and in the local DRL repo
- [ ] Retire or redirect the legacy Cloud Run URL if it is no longer intended to be public.
  - It still responds, so this is now a deployment/cloud cleanup item rather than an AIX-code item.
  - [ ] Retrieve and use the data collected from gameplay at the older "ugly" location

## /lunar
- [ ] "session was not found" now appears immediately and then every few steps thereafter running Lunar demo. Both Machine Play and Human Play are effected. Repeatedly hitting "Run" or "Step" works a few steps at a time (or with Human, same with any key strike: intermittent response, mostly "session not found"). Did not used to be this way before the changeover from https://drl-web-83735348592.us-west3.run.app/lunar (which is still up, and doesn't have this problem)
  - [ ] Examine.
  - [ ] Discuss.
  - [ ] Fix.
