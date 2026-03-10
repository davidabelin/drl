"""Curated narrative content for the interactive demo pages.

The demo services compute numbers and charts. This module provides the
human-facing layer that explains where each demo came from in the repository,
which ideas it is preserving, and which adjacent materials should be reviewed
next when the user wants to go deeper than the interactive surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True, slots=True)
class DemoCard:
    """One explanatory card that adds context around a live demo."""

    kicker: str
    title: str
    body: str
    points: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DemoReference:
    """One source trail item that points back into the DRL archive."""

    label: str
    kind: str
    path: str
    note: str


@dataclass(frozen=True, slots=True)
class GlossaryTerm:
    """One short definition used to make the demo readable to newcomers."""

    term: str
    meaning: str


@dataclass(frozen=True, slots=True)
class DemoGuide:
    """Narrative scaffolding for a specific interactive demo."""

    slug: str
    overview_title: str
    overview_body: str
    cards: tuple[DemoCard, ...]
    source_refs: tuple[DemoReference, ...]
    glossary: tuple[GlossaryTerm, ...]
    keeps: tuple[str, ...]
    omits: tuple[str, ...]
    next_steps: tuple[str, ...]


def _card(kicker: str, title: str, body: str, *points: str) -> DemoCard:
    """Build a small explanatory card with optional bullet points."""

    return DemoCard(kicker=kicker, title=title, body=body, points=points)


def _ref(label: str, kind: str, path: str, note: str) -> DemoReference:
    """Build one source-trail reference entry."""

    return DemoReference(label=label, kind=kind, path=path, note=note)


def _term(term: str, meaning: str) -> GlossaryTerm:
    """Build one glossary term."""

    return GlossaryTerm(term=term, meaning=meaning)


@lru_cache(maxsize=1)
def get_demo_guides() -> dict[str, DemoGuide]:
    """Return the structured narrative content used by the demo templates.

    The mapping is cached because the content is static for the lifetime of the
    app process. Keeping it in one place makes the templates simpler and avoids
    hiding important educational framing inside route functions.
    """

    return {
        "finance": DemoGuide(
            slug="finance",
            overview_title="Why this finance demo matters",
            overview_body=(
                "The original finance notebook does more than draw a schedule. It reframes optimal liquidation as a reinforcement-learning problem with "
                "states, actions, and rewards, then compares learned behavior against the Almgren-Chriss benchmark. This page intentionally starts from "
                "the benchmark so the core trade-off is visible before any actor-critic training enters the picture."
            ),
            cards=(
                _card(
                    "From the notebook",
                    "How the repo framed optimal execution",
                    "The finance notebook defines the state as recent log returns plus normalized time and remaining inventory. The action is the fraction "
                    "of the remaining position to sell now. The reward is based on improvement in Almgren-Chriss utility after each step.",
                ),
                _card(
                    "Why this demo starts here",
                    "Closed-form first, policy learning second",
                    "The archived notebook eventually moves into DDPG. For a no-code public demo, the analytical schedule in `syntheticChrissAlmgren.py` is "
                    "the better first surface because it shows exactly what the agent is trying to balance before neural networks make the picture noisier.",
                ),
                _card(
                    "What to notice",
                    "Three controls, one tension",
                    "Each slider changes the balance between impact and uncertainty.",
                    "Longer liquidation windows usually lower market impact but leave you exposed to more price noise.",
                    "More trades make each sale smaller, which smooths the schedule and softens individual shocks.",
                    "Higher risk aversion pushes the policy to sell earlier and reduces the schedule half-life.",
                ),
                _card(
                    "Bridge to the rest of the repo",
                    "Why this belongs inside a DRL arm",
                    "Finance looks different from CartPole or Reacher, but the structure is familiar: a state, a policy, a reward signal, and a sequential "
                    "trade-off under uncertainty. It is one of the cleanest examples in the archive of DRL being used as an application rather than just a toy benchmark.",
                ),
            ),
            source_refs=(
                _ref(
                    "Finance notebook",
                    "notebook",
                    "source-material/finance/DRL.ipynb",
                    "Introduces the liquidation problem, defines states/actions/rewards, and sketches the actor-critic training loop.",
                ),
                _ref(
                    "Market environment",
                    "python module",
                    "source-material/finance/syntheticChrissAlmgren.py",
                    "Implements the linear-impact Almgren-Chriss simulator and the closed-form trade schedule used by this demo.",
                ),
                _ref(
                    "Finance helpers",
                    "python module",
                    "source-material/finance/utils.py",
                    "Contains plotting and table helpers from the notebook-oriented workflow.",
                ),
                _ref(
                    "Finance models",
                    "python module",
                    "source-material/finance/model.py",
                    "Defines the actor and critic networks used when the notebook escalates from the benchmark to learned policies.",
                ),
                _ref(
                    "Actor-critic transcripts",
                    "transcript set",
                    "source-material/classwork/ContinuousControl_Transcripts",
                    "Background material that connects the finance notebook's RL framing to the broader actor-critic branch in the repo.",
                ),
            ),
            glossary=(
                _term(
                    "Implementation shortfall",
                    "The gap between the portfolio's paper value at the starting price and the cash you actually realize while selling.",
                ),
                _term(
                    "Expected shortfall",
                    "The systematic execution cost created by spread and price impact, even before random price motion is considered.",
                ),
                _term(
                    "Variance",
                    "The uncertainty caused by prices wandering while you are still trying to finish the sale.",
                ),
                _term(
                    "Risk aversion (lambda)",
                    "The weight that says how much you care about uncertainty relative to pure execution cost.",
                ),
                _term(
                    "Temporary impact",
                    "The immediate price concession paid on the shares sold right now.",
                ),
                _term(
                    "Permanent impact",
                    "The lingering price effect of having traded a large amount into the market.",
                ),
            ),
            keeps=(
                "The one-million-share setup, the liquidation horizon, and the linear impact assumptions from the old simulator.",
                "The core Almgren-Chriss trade-off between expected shortfall and variance.",
                "The same intuition the notebook uses before it introduces actor-critic training.",
            ),
            omits=(
                "The DDPG training loop, replay memory, and network optimization details.",
                "Random trajectory rollouts and noisy realized price paths from a training run.",
                "Microstructure details like order books, fees, and latency that the notebook explicitly treats as future extensions.",
            ),
            next_steps=(
                "Promote a static explainer about states/actions/rewards from the finance notebook into its own subpage.",
                "Add a replayable comparison between the closed-form benchmark and a saved learned policy once a stable checkpoint exists.",
                "Cross-link this branch more explicitly with the Policy Gradients and Continuous Control arms.",
            ),
        ),
        "foundations": DemoGuide(
            slug="foundations",
            overview_title="Why this foundations demo matters",
            overview_body=(
                "The dynamic-programming notebook is the cleanest point in the archive where reinforcement learning still fits in your head all at once. "
                "This demo isolates the value-iteration part of that notebook so users can see how values propagate through a map before later sections "
                "replace exact tables with sampling, approximation, and deep networks."
            ),
            cards=(
                _card(
                    "From the coursework",
                    "The original notebook sequence",
                    "The archived dynamic-programming material walks step-by-step through iterative policy evaluation, recovering q-values from v-values, "
                    "policy improvement, policy iteration, truncated policy iteration, and finally value iteration on a slippery FrozenLake environment.",
                ),
                _card(
                    "Why value iteration first",
                    "The shortest path from planning to RL intuition",
                    "Value iteration compresses the whole planning loop into repeated Bellman optimality backups. That makes it the best visual bridge from exact tabular reasoning "
                    "to the approximate value updates you later see in Monte Carlo control, temporal-difference learning, Q-learning, and DQN.",
                ),
                _card(
                    "What to notice",
                    "The map reacts to three kinds of pressure",
                    "The grid is small enough that you can watch the trade-offs directly.",
                    "Higher discount lets the goal's value propagate farther backward through the map.",
                    "Higher slip makes tiles near holes less attractive because intended moves can fail.",
                    "A more negative living reward makes lingering expensive and favors shorter paths.",
                ),
                _card(
                    "Bridge to later sections",
                    "Why this still matters after deep learning arrives",
                    "Once the state space gets too large, exact tabular updates stop being practical. But the logic does not disappear. DQN, actor-critic methods, and other later "
                    "algorithms still revolve around estimating future return and improving actions using that estimate.",
                ),
            ),
            source_refs=(
                _ref(
                    "Dynamic Programming notebook",
                    "notebook",
                    "source-material/dynamic-programming/Dynamic_Programming.ipynb",
                    "Primary coursework notebook for policy evaluation, policy iteration, truncated policy iteration, and value iteration.",
                ),
                _ref(
                    "Dynamic Programming solution",
                    "notebook",
                    "source-material/dynamic-programming/Dynamic_Programming_Solution.ipynb",
                    "Canonical solutions to the same exercises, useful when reconstructing exact update rules.",
                ),
                _ref(
                    "FrozenLake environment",
                    "python module",
                    "source-material/dynamic-programming/frozenlake.py",
                    "The archived custom environment that defines the same 4x4 map and slippery transition idea used here.",
                ),
                _ref(
                    "Monte Carlo notebook",
                    "notebook",
                    "source-material/monte-carlo/Monte_Carlo.ipynb",
                    "Shows what changes when the agent stops assuming full transition knowledge and starts learning from sampled episodes.",
                ),
                _ref(
                    "Temporal Difference notebook",
                    "notebook",
                    "source-material/temporal-difference/Temporal_Difference.ipynb",
                    "Extends the story from exact planning into Sarsa, Q-learning, and Expected Sarsa.",
                ),
                _ref(
                    "Course cheatsheet",
                    "pdf",
                    "source-material/classwork/cheatsheet.pdf",
                    "Compact reference sheet for the value-function and policy-update family used across the foundations material.",
                ),
            ),
            glossary=(
                _term(
                    "Value function",
                    "A score for how promising a state is if you follow a policy from there onward.",
                ),
                _term(
                    "Bellman backup",
                    "One update that rewrites a state's value using immediate reward plus discounted estimates of what comes next.",
                ),
                _term(
                    "Policy improvement",
                    "The step where you turn current value estimates into better action choices.",
                ),
                _term(
                    "Discount factor (gamma)",
                    "The number between 0 and 1 that controls how strongly distant rewards matter today.",
                ),
                _term(
                    "Slip probability",
                    "The chance that the environment moves you sideways instead of where you intended to go.",
                ),
                _term(
                    "Living reward",
                    "The reward or penalty you receive simply for taking another step before the episode ends.",
                ),
            ),
            keeps=(
                "The classic 4x4 FrozenLake layout and the central idea of slippery transitions from the archived coursework.",
                "Exact value-iteration style planning rather than sampled learning.",
                "The visual intuition that the goal pulls value backward while hazards repel it.",
            ),
            omits=(
                "The coding exercises for iterative policy evaluation, q_pi extraction, and policy iteration.",
                "The Gym-dependent course scaffolding, rendering helpers, and solution-checking utilities.",
                "The broader step into Monte Carlo and temporal-difference learning, which remain separate review branches.",
            ),
            next_steps=(
                "Add a follow-on demo that compares value iteration with Monte Carlo or Q-learning on the same map.",
                "Port a lightweight glossary or formula shelf from the coursework notebooks and cheatsheet.",
                "Use this page as the front door into the Value-Based arm so the transition to DQN feels continuous instead of abrupt.",
            ),
        ),
    }
