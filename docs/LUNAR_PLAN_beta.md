# Lunar Lander Beta Plan: Machine Continuous Control

## Summary
- Add a machine-play-only continuous-control lane to the existing Lunar page, using `LunarLanderContinuous-v3` when available.
- Reuse the current DRL-local session and checkpoint flow where possible, but keep the first beta narrower than the discrete DQN lane.
- Treat `DDPG`-style playback and evaluation as the first continuous milestone. Human continuous control and in-browser continuous training are explicitly deferred.

## Why this is the right beta
- The repo already contains multiple continuous Lunar paths under `source-material/lunar/ddpg` and `source-material/lunar/dqn2ddpg`.
- Continuous Lunar is the cleanest bridge from the current discrete recovery work into actor-critic control without jumping all the way to the older Unity Reacher stack.
- Machine play is the smallest useful slice because it avoids solving browser-friendly throttle controls before the runtime and checkpoint story are stable.

## Scope

### In scope
- Continuous machine playback for one selected checkpoint at a time
- Continuous-session reset, run, pause, and single-step controls
- Continuous action telemetry for the main engine and side thruster values
- Checkpoint discovery for continuous Lunar actor weights plus metadata
- Local evaluation jobs for continuous checkpoints
- Curated guide content that explains continuous state/action semantics

### Out of scope
- Human continuous control in the browser
- Arbitrary continuous-policy code editing from the current Lunar training editor
- Full recovery of every historical PPO/DDPG notebook path
- Cross-instance shared session storage for App Engine

## Implementation Changes

### Runtime and sessions
- Add a second runtime adapter for `LunarLanderContinuous-v3`, with fallback to `v2` only if required by the installed Gymnasium stack.
- Extend the Lunar session payload to advertise a controller variant such as `discrete-dqn`, `continuous-ddpg`, or `continuous-baseline`.
- Continuous step payloads should return:
  - rendered frame
  - 2-value continuous action vector
  - immediate reward
  - cumulative score
  - done and truncated flags
  - step index
  - raw 8-element environment state vector
- Keep continuous sessions machine-only in beta. The browser does not send raw throttle vectors yet.

### Checkpoints and jobs
- Introduce continuous checkpoint metadata alongside the existing discrete catalog, rather than pretending both checkpoint families are interchangeable.
- Beta checkpoint shape should record:
  - `variant: continuous-ddpg`
  - actor checkpoint path
  - optional critic checkpoint path
  - source snapshot path
  - environment id
  - training summary and evaluation summary
- Reuse the current job table and artifact root, but add a continuous variant flag instead of creating a separate job system.
- First continuous job kind should be evaluation-only unless a stable training harness is recovered cleanly from the archive.

### UI and page structure
- Keep one `/lunar` page.
- Add a clear machine-play mode switch between:
  - discrete heuristic / learned checkpoints
  - continuous checkpoints
- In continuous mode:
  - hide discrete action buttons
  - show action telemetry as `main engine` and `side thruster`
  - keep `run`, `pause`, `step`, `reset`, and playback-speed controls
  - label the checkpoint family clearly so users know they are not watching the discrete DQN path

### Source recovery path
- Prefer `source-material/lunar/ddpg` as the canonical first recovery branch.
- Use `source-material/lunar/dqn2ddpg` as a secondary reference when metadata or helper code is clearer there.
- Do not merge multiple archived training styles into one beta harness unless their checkpoint formats are already compatible.

## Acceptance Criteria
- The Lunar page can load at least one continuous checkpoint and play it back without user-supplied manual actions.
- Reset, step, run, and pause all behave correctly for continuous sessions.
- The page exposes readable action telemetry and score updates while the continuous policy runs.
- Continuous checkpoint summaries are discoverable through the existing API family.
- Continuous evaluation jobs can run locally and persist results back into checkpoint metadata.

## Test Plan
- Unit-test the continuous environment adapter and action-vector serialization.
- Add Flask tests for:
  - listing continuous checkpoints
  - starting a continuous machine session
  - stepping and resetting that session
  - retrieving continuous checkpoint summaries
- Add one smoke evaluation test for a tiny continuous checkpoint fixture or a deterministic stub controller if a real archived checkpoint is not yet stable.

## Risks and Notes
- Continuous checkpoint recovery may be slowed by inconsistent archived naming and notebook-export code style.
- Continuous Lunar playback on App Engine still inherits the current single-instance session assumptions.
- Human continuous control should be treated as a separate plan, not quietly folded into this one.
