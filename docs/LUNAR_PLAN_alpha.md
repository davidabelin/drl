# Lunar Lander First-Pass Recovery Plan

## Summary
- Add a dedicated Lunar Lander page inside the existing DRL app, linked from the `Value-Based` arm and referenced from `Archive`.
- Make the first milestone Gym-first and local-first: restore a real discrete LunarLander runtime, train a fresh learned policy, and expose three user-facing surfaces on one page: `Play`, `Machine Play`, and `Training`.
- Use the lunar DQN branch as the first live recovery path. Treat PPO, DDPG, and continuous LunarLander as later expansion, not part of the first runnable milestone.

## Implementation Changes
- Runtime and trainer
  - Implement a backend environment adapter for discrete LunarLander using Gymnasium, targeting `LunarLander-v3` when available and falling back to `LunarLander-v2` only if required by the runtime.
  - Base the first learned-policy pipeline on the discrete lunar DQN materials, not PPO or DDPG.
  - Use the current local DRL/AIX Python environment for v1 runtime and training jobs; add the needed Lunar stack there instead of introducing a separate worker service in the first milestone.
  - Add a DRL-local job manager, modeled on the existing Polyfolds job flow, with configurable roots such as `DRL_LUNAR_JOBS_ROOT` and optional interpreter override `DRL_LUNAR_RUNTIME_PYTHON`.
  - Support exactly two job kinds in v1: `train` and `evaluate`.
  - Persist per-job artifacts in a fixed shape: `metadata.json`, `stdout/stderr` logs, `metrics.jsonl`, `best_checkpoint.pt`, `latest_checkpoint.pt`, `evaluation.json`, and the submitted editable source snapshot.

- Page and UX
  - Add one Lunar page with three panes/tabs: `Play`, `Machine Play`, and `Training`.
  - `Play` uses a real backend-controlled episode session with discrete action controls: `No-op`, `Left`, `Main`, `Right`. Keyboard defaults are `Space`, `ArrowLeft`, `ArrowUp`, and `ArrowRight`, with matching on-screen buttons.
  - `Machine Play` lets the user choose a trained checkpoint and then `run`, `pause`, `step`, `reset`, and adjust playback speed while viewing real env frames and live telemetry.
  - `Training` uses an embedded Ace editor with a fixed DQN experiment template. The editable surface is intentionally bounded to a DQN recipe: hyperparameters block, network-width block, epsilon schedule, and reward-shaping helper. Training always runs through a fixed harness; arbitrary imports, arbitrary file writes, and shell access are out of scope.
  - Save each submitted editor snapshot alongside the job so every checkpoint shown in the UI is reproducible from a specific training script revision.

- API and interfaces
  - Add live-session APIs:
    - `POST /api/v1/lunar/sessions`
    - `POST /api/v1/lunar/sessions/<session_id>/step`
    - `POST /api/v1/lunar/sessions/<session_id>/reset`
    - `DELETE /api/v1/lunar/sessions/<session_id>`
  - Add checkpoint APIs:
    - `GET /api/v1/lunar/checkpoints`
    - `GET /api/v1/lunar/checkpoints/<checkpoint_id>/summary`
  - Add job APIs:
    - `POST /api/v1/lunar/jobs`
    - `GET /api/v1/lunar/jobs`
    - `GET /api/v1/lunar/jobs/<job_id>`
  - Session-step responses must return the rendered frame plus: action taken, immediate reward, cumulative score, done/truncated flags, step index, and the raw 8-element LunarLander state vector.
  - Job records must include status, artifact paths, submitted source snapshot path, and any checkpoint ids promoted into the machine-play selector.
  - Promote one checkpoint to “featured” only after it meets the first acceptance gate: mean evaluation score `>= 100` over 20 seeded episodes.

- Content and curation
  - Add a Lunar guide with the same depth as Finance and Foundations: branch map, DQN-first rationale, state/action/reward glossary, discrete-vs-continuous explanation, and an explicit split between “live now” and “archive later.”
  - Surface the lunar notebooks and helper modules as source references, but keep only the discrete DQN runtime path live in v1.
  - Mark PPO, DDPG, and continuous LunarLander as planned follow-ons, not half-supported controls.

## Test Plan
- Backend
  - Unit-test the environment adapter, discrete action mapping, frame serialization, and session lifecycle.
  - Unit-test job submission, job status transitions, artifact registration, checkpoint discovery, and failure paths.
  - Add a smoke trainer run with very small episode counts and a smoke evaluation job that consumes its output checkpoint.
- API
  - Add Flask tests for all `/api/v1/lunar/*` endpoints, including invalid actions, invalid session ids, missing checkpoints, failed jobs, and mounted `/drl/...` behavior through AIX.
  - Verify that a completed training job produces a discoverable checkpoint and that evaluation jobs can consume it.
- UI/manual
  - Verify keyboard human play, visible reward/score/state updates, and episode reset behavior.
  - Verify trained-agent playback `run/pause/step/reset/speed` controls.
  - Verify editor load/edit/submit flow, job log visibility, artifact discovery, and promotion of the best checkpoint into the checkpoint selector.
  - Manual acceptance for the featured checkpoint: visibly competent machine-play rollouts and an evaluation report meeting the `>= 100` mean-score gate.

## Assumptions and Defaults
- Discrete LunarLander is the only live runtime target in the first milestone.
- Learned-policy-first means fresh retraining only. No time is budgeted for historical checkpoint recovery.
- The first live learned agent is DQN-based.
- The training playground is local-first. Public-safe arbitrary-code execution, multi-tenant hardening, and deployment-safe sandboxing are explicitly deferred.
- The DRL app remains the owning surface. No new AIX mount is introduced; Lunar is implemented as a richer subpage and API family inside the existing DRL lab.
