# Turn-Based Multi-Agent Demo Plan

## Chosen game
`Connect Four`

## Why this is the right first game
- It is genuinely multi-agent, strictly turn-based, and easy to understand on sight.
- It needs no external engine, Unity runtime, or heavyweight asset recovery.
- The action space is bounded and clean: choose one of 7 columns.
- It supports the full ladder of useful demo modes:
  - human vs heuristic
  - human vs learned agent
  - heuristic vs learned agent
  - self-play training and evaluation
- It is meaningfully deeper than Tic-Tac-Toe without becoming visually or computationally messy.

## Why not use the archived Tennis or Soccer environments first
- Those environments are conceptually valuable, but the binaries are not present in this repo.
- They are continuous and real-time, which is the opposite of the “quickly build a clear web demo” requirement.
- They are better as theory context for the new demo than as the first runtime target.

## Product goal
Build a small, self-contained multi-agent page that demonstrates adversarial RL and self-play in a form that is easy to run locally and easy to explain to users.

## First milestone
- Render a playable Connect Four board on the DRL site.
- Support human-vs-baseline and baseline-vs-baseline play first.
- Expose state, action, reward, and terminal outcome clearly.
- Leave learned-policy training as the second phase, not the first.

## Implementation Plan

### Backend
- Add a lightweight Python environment for Connect Four with:
  - 6 rows x 7 columns
  - alternating turns
  - legal-move validation
  - win, loss, and draw detection
  - JSON-serializable board state
- Add session APIs parallel to the existing Lunar pattern, but simpler:
  - create game
  - drop piece
  - reset game
  - delete game
- Add one strong baseline before any RL training:
  - immediate win / block checks
  - center-column preference
  - shallow lookahead if needed

### Frontend
- Add a dedicated multi-agent demo page instead of burying the game inside the catalog text.
- Show:
  - board state
  - current player
  - legal columns
  - latest move
  - winner or draw status
- Include a small explainer panel that maps the game to RL:
  - state: board + current player
  - action: chosen column
  - reward: win, loss, draw, illegal move penalty if used
  - training style: self-play against historical or heuristic opponents

### Learning path
- Phase 1: deterministic baseline agents only
- Phase 2: tabular or compact-network self-play training offline
- Phase 3: checkpoint catalog and machine-play replay inside the site

## Acceptance Criteria
- A user can open the page and finish a complete human-vs-baseline game.
- The game state is recoverable and resettable through a small API surface.
- The baseline is strong enough that the page feels like a real opponent, not a random move generator.
- The page explains why this is a multi-agent RL problem and how self-play would fit.

## Future extensions
- Add learned-policy checkpoints after the basic gameplay loop is stable.
- Add position-value or action-value overlays to show what the current agent prefers.
- If cooperation is still desired after the adversarial lane is stable, add a second custom grid game rather than overloading Connect Four with goals it does not serve well.
