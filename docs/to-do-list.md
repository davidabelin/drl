# DRL Rolling List of Changes To Make

Status refresh: 2026-03-25

## Quick and Easy
- [ ] Retire or redirect the legacy Cloud Run URL if it is no longer intended to be public.
- [] Plan in `docs\LUNAR_PLAN_beta.md` for machine continuous control.
- [x] Highlight the ML-chosen path in `/foundations` Frozen Lake.
- [x] Improve the `/finance` explanations so they relate more clearly to finance and to what the ML is doing.
- [] Discuss or shortlist additional interactive labs for `/sections/value-based`.
- [x] Assess whether the Bananas project(s) are worth reviving.
- [] Choose the turn-based multi-agent game.
- [] Plan the multi-agent RL demo implementation.
- [ ] Hard-delete any `scripts\*.bat` files no longer needed.
  - Current assessment: no safe deletions yet; each current `.bat` file still has a distinct role or is referenced by docs/scripts.

## Long and Hard
- [ ] Retrieve and use the data collected from gameplay at the older legacy URL.
- [ ] If Lunar playback still feels too slow, reduce per-step round-trip cost or move live session state to a shared backend.
- [ ] Build human continuous control for Lunar Lander.
- [ ] Implement machine continuous control for Lunar Lander.
- [ ] Make `/foundations` Frozen Lake look and feel more like Frozen Lake.
- [ ] Add more `/foundations` game options if they improve the demo.
- [ ] Implement more Gymnasium envs with a natural transition toward continuous control.
- [ ] Implement the turn-based multi-agent RL demo.
- [ ] Condense the scripts into 4 regular-use files.

## Legacy Cloud Run Host
- [x] Replace the ugly generated DRL URL as the canonical entry point.
  - Current canonical DRL URL is `https://deeprl-031026.wm.r.appspot.com/`
- [ ] Retire or redirect the legacy Cloud Run URL if it is no longer intended to be public.
  - It still responds, so this is now a deployment/cloud cleanup item rather than a code item.
  - This still needs an explicit choice about whether the old URL should hard-redirect, serve a retirement notice, or be made private.
  - [ ] Retrieve and use the data collected from gameplay at the older "ugly" location

## Lunar Lander
- [x] Fix the App Engine lunar live-play regression.
  - Symptom: the canonical App Engine host is slower/clunkier than Cloud Run and intermittently returns `session was not found` during both Human Play and Machine Play.
  - [x] Examine.
  - [x] Discuss.
  - [x] Confirm the repo stores live Lunar sessions in process-local memory (`LunarSessionManager._sessions`), so requests that land on a different App Engine instance cannot see the same session.
  - [x] Confirm the current public App Engine host reproduces the issue, while the legacy Cloud Run hosts do not.
  - [x] Commit the first App Engine mitigation in `app.yaml`: enable session affinity, pin the service to one instance, and request more realistic CPU/RAM for the Gym/Torch runtime.
  - [x] Redeploy App Engine and verify Human Play and Machine Play both stay on one session without intermittent 404s.
  - [_] If playback still feels too slow after the session fix, reduce per-step round-trip cost or move live session state to a shared backend.
- [] **Continuous control**
  - [] human cc first
  - [] machine cc implementation plan as `docs\LUNAR_PLAN_beta.md`
  - [] implement cc ml

## /foundations
- [ ] frozen lake:
 - [ ] a more "frozen-lake"-like display/graphics
 - [x] highlight ML-chosen path
 - [ ] more "game" options, if fun!

## /finance
- [x] better explanations for users -- relate to finance and describe the RL framing
- [ ] more on ML behind it and what it's doing

##  /sections/value-based
- [x] Discuss additional interactive labs for this section:
 - shortlist written in `docs\value-based-labs-shortlist.md`
 - recommended order: `CartPole`, then `Taxi`, then `MountainCar`
 - [x] Bananas assessment: keep as archive/playback later, not as the next live lab

## Multi-agent Gameplay -- *high priority*
- [x] Made a **priority**
  - experience to be used for a separate project, but easier to present here
- [] Design a turn-based multi-player game as RL demo
  - [] choose a game: **not**`Connect Four`, not poker
  - [] PLAN implementation in `docs\multi-agent-turn-based-plan.md`
  - [] implement 

## Scripts
- [x] Intro and in-line documentation for each script file
- [] Hard-delete any scripts\*.bat no longer needed
  - current assessment: no safe deletions yet; revisit after the legacy Cloud Run decision
- [] condense everything into 4 regular-use files, to: set env, show status, configure drl env, deploy drl web app

## Reacher-like lab: self-play learning example
- [] Does not have to be Reacher or use the Reacher env; something *similar* and implementable in *any* easier way
