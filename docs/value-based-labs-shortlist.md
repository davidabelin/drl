# Value-Based Next Labs Shortlist

## Recommendation
- Build `CartPole` next if the goal is the smoothest path from tabular ideas into DQN-style control.
- Build `Taxi` next if the goal is the most self-contained discrete lab with minimal runtime friction.
- Keep `MountainCar` as the delayed-reward bridge if you want a stronger lesson about shaping and credit assignment.
- Do not make `Bananas` the next live lab.

## Ranked options

### 1. CartPole
- Best overall next step for the current site.
- It keeps the action space tiny and readable.
- It creates a clean narrative line from Frozen Lake and tabular value ideas to function approximation and DQN.
- It is already familiar enough that the UI can focus on policy behavior instead of teaching game rules.

### 2. Taxi
- Best low-risk implementation candidate.
- The repo already includes a self-contained Taxi branch under `source-material/taxi`.
- It supports state, action, and reward explanations without Unity baggage or heavy assets.
- It fits the current DRL app style well: small environment, clear controls, and obvious policy traces.

### 3. MountainCar
- Best conceptual bridge into harder control problems.
- It teaches delayed reward, exploration pressure, and why naive greedy behavior fails.
- It is a better “you need to build momentum” lesson than CartPole, but a worse first follow-up if the priority is frictionless polish.

## Bananas verdict
- Worth reviving as archive material or a later playback-only showcase.
- Not worth making the next live interactive lab.

## Why Bananas should not be next
- It depends on the older Unity environment path instead of the modern self-contained Python demos already working in this repo.
- The web app would need more runtime recovery work before the actual lesson becomes visible.
- It overlaps conceptually with the existing value-based and Lunar material, but with substantially more environment friction.
- The real near-term value is historical: it shows your project progression from tutorial DQN into a full navigation project.

## Best use of Bananas now
- Keep it visible on the `Value-Based` section page as a curated archive asset.
- Optionally recover the archived weights from `p1_project.zip` and present a static or replay-oriented artifact view later.
- Use it as a case-study page before turning it into a live runtime.

## Suggested order
1. CartPole
2. Taxi
3. MountainCar
4. Bananas playback/archive recovery
