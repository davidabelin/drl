# DRL Rolling List of Changes To Make

Status refresh: 2026-03-22

## Legacy URL: `https://drl-web-x2ulcmhaiq-wm.a.run.app/`
- [x] Replace the ugly generated DRL URL as the canonical entry point.
  - Current canonical DRL URL is `https://deeprl-031026.wm.r.appspot.com/`
  - AIX already points to the canonical App Engine URL, and that canonical URL serves the updated chrome
- [x] Change `Back to AIX Hub` to `AIX Labs` and point it to AIX.
  - Verified on the canonical App Engine DRL URL and in the local DRL repo
- [ ] Retire or redirect the legacy Cloud Run URL if it is no longer intended to be public.
  - It still responds, so this is now a deployment/cloud cleanup item rather than an AIX-code item.
  - [ ] Retrieve and use the data collected from gameplay at the older "ugly" location

## front page
- []

## /lunar
- [ ] Fix the App Engine lunar live-play regression.
  - Symptom: the canonical App Engine host is slower/clunkier than Cloud Run and intermittently returns `session was not found` during both Human Play and Machine Play.
  - [x] Examine.
  - [x] Discuss.
  - [x] Confirm the repo stores live Lunar sessions in process-local memory (`LunarSessionManager._sessions`), so requests that land on a different App Engine instance cannot see the same session.
  - [x] Confirm the current public App Engine host reproduces the issue, while the legacy Cloud Run hosts do not.
  - [x] Commit the first App Engine mitigation in `app.yaml`: enable session affinity, pin the service to one instance, and request more realistic CPU/RAM for the Gym/Torch runtime.
  - [ ] Redeploy App Engine and verify Human Play and Machine Play both stay on one session without intermittent 404s.
  - [ ] If playback still feels too slow after the session fix, reduce per-step round-trip cost or move live session state to a shared backend.

##  /finance
- []
