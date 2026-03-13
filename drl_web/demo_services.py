"""Interactive demo services for finance and foundations pages.

This module converts archival notebook ideas into deterministic, web-friendly
payload builders. Each builder accepts a small set of user controls and returns
JSON-serializable data for templates and API endpoints, without depending on
notebook state, plotting backends, or long-running training loops.
"""

from __future__ import annotations

from functools import lru_cache
from importlib.util import module_from_spec, spec_from_file_location
from math import isfinite
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
FINANCE_MODULE_PATH = ROOT / "source-material" / "finance" / "syntheticChrissAlmgren.py"


def _load_finance_module():
    """Load the archived finance simulator module directly from disk."""

    spec = spec_from_file_location("drl_finance_env", FINANCE_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load finance module from {FINANCE_MODULE_PATH}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def _market_environment_cls():
    """Return the cached finance ``MarketEnvironment`` class."""

    return getattr(_load_finance_module(), "MarketEnvironment")


def _finance_fallback_metrics(
    *,
    liquidation_days: int,
    num_trades: int,
    risk_aversion: float,
    first_trade_fraction: float,
) -> tuple[float, float, float, float]:
    """Return approximate finance metrics when the archive module is unavailable.

    The deployed site should remain usable even if the raw notebook-era finance
    files are absent from the container image. These formulas are deliberately
    simple and pedagogical: they preserve the directional relationships between
    urgency, impact, and price risk without pretending to be the original
    Almgren-Chriss implementation.
    """

    inventory_value = 50_000_000.0
    normalized_horizon = liquidation_days / 60.0
    normalized_granularity = num_trades / max(liquidation_days, 1)
    urgency = float(np.clip((np.log10(risk_aversion) + 7.0) / 3.0, 0.0, 1.0))

    impact_component = 0.0007 + 0.0013 * first_trade_fraction + 0.00055 / max(normalized_horizon, 0.25)
    slicing_component = 0.00022 / max(normalized_granularity + 0.15, 0.2)
    risk_component = 0.00035 + 0.00115 * urgency + 0.00045 * max(normalized_horizon - 0.55, 0.0)

    expected_shortfall = inventory_value * (impact_component + slicing_component)
    std_dev = inventory_value * risk_component
    variance = std_dev**2
    utility = expected_shortfall + (risk_aversion * variance)
    half_life = max(1.0, liquidation_days / (1.0 + 5.0 * urgency))
    return expected_shortfall, std_dev, utility, half_life


def _build_finance_demo_fallback(*, liquidation_days: int, num_trades: int, risk_aversion: float) -> dict:
    """Return an approximate finance payload without importing archive code."""

    total_shares = 1_000_000
    starting_price = 50.0
    trade_index = np.arange(num_trades, dtype=np.float64)
    urgency = float(np.clip((np.log10(risk_aversion) + 7.0) / 3.0, 0.0, 1.0))
    decay = 0.035 + 0.22 * urgency + 0.08 * max(0.0, (60.0 - liquidation_days) / 60.0)
    weights = np.exp(-decay * trade_index)
    weights = weights / weights.sum()
    trade_list = np.round(weights * total_shares)
    residual = int(total_shares - int(trade_list.sum()))
    if residual != 0:
        trade_list[-1] += residual
    remaining = (np.ones(num_trades) * total_shares) - np.cumsum(trade_list)

    first_trade_fraction = float(trade_list[0] / total_shares)
    expected_shortfall, std_dev, utility, half_life = _finance_fallback_metrics(
        liquidation_days=liquidation_days,
        num_trades=num_trades,
        risk_aversion=risk_aversion,
        first_trade_fraction=first_trade_fraction,
    )

    frontier_points = []
    for point in np.geomspace(1e-7, 1e-4, 28):
        frontier_trade_fraction = float(
            np.exp(-(0.035 + 0.22 * np.clip((np.log10(point) + 7.0) / 3.0, 0.0, 1.0))) / np.exp(
                -(0.035 + 0.22 * np.clip((np.log10(point) + 7.0) / 3.0, 0.0, 1.0)) * np.arange(num_trades)
            ).sum()
        )
        frontier_shortfall, frontier_std, _, _ = _finance_fallback_metrics(
            liquidation_days=liquidation_days,
            num_trades=num_trades,
            risk_aversion=float(point),
            first_trade_fraction=frontier_trade_fraction,
        )
        frontier_points.append(
            {
                "risk_aversion": float(point),
                "expected_shortfall": float(frontier_shortfall),
                "std_dev": float(frontier_std),
            }
        )

    return {
        "controls": {
            "liquidation_days": liquidation_days,
            "num_trades": num_trades,
            "risk_aversion": risk_aversion,
        },
        "metrics": {
            "shares_total": int(total_shares),
            "starting_price": float(starting_price),
            "expected_shortfall": float(expected_shortfall),
            "std_dev": float(std_dev),
            "utility": float(utility),
            "half_life": float(half_life),
            "first_trade_fraction": float(first_trade_fraction),
            "average_trade_size": float(np.mean(trade_list)),
        },
        "series": {
            "trade_list": [int(value) for value in trade_list.tolist()],
            "remaining": [int(max(value, 0)) for value in remaining.tolist()],
            "frontier": frontier_points,
        },
        "story": {
            "headline": "Optimal execution turns a big sale into a timing problem, not just a math problem.",
            "body": _finance_story(first_trade_fraction, risk_aversion),
        },
        "source_mode": "fallback",
        "source_note": "Archive module unavailable in this runtime, so the demo is using a faithful approximation of the same trade-offs.",
    }


def finance_presets() -> tuple[dict, ...]:
    """Return preset control values for the finance demo.

    The presets are named for the execution style they imply so the UI can stay
    readable for users who do not already know the underlying notation.
    """

    return (
        {
            "label": "Balanced",
            "liquidation_days": 60,
            "num_trades": 60,
            "risk_aversion": 1e-6,
            "summary": "A middle-ground liquidation plan that balances market impact against price risk.",
        },
        {
            "label": "Patient",
            "liquidation_days": 100,
            "num_trades": 100,
            "risk_aversion": 2e-7,
            "summary": "You are willing to stay in the market longer to avoid pushing the price around.",
        },
        {
            "label": "Urgent",
            "liquidation_days": 30,
            "num_trades": 30,
            "risk_aversion": 8e-6,
            "summary": "You care more about price uncertainty, so the plan sells faster and front-loads inventory.",
        },
    )


def _round_trade_list(trade_list: np.ndarray) -> np.ndarray:
    """Round a continuous analytical trade list to whole shares.

    The archived environment computes real-valued trade sizes. The demo rounds
    them for legibility, then pushes any residual back into the last non-zero
    trade so the displayed schedule still sums to the full inventory.
    """

    rounded = np.around(trade_list)
    residual = np.around(trade_list.sum() - rounded.sum())
    if residual != 0:
        nonzero = np.nonzero(rounded)[0]
        if len(nonzero):
            rounded[nonzero[-1]] += residual
    return rounded


def _finance_story(first_trade_fraction: float, risk_aversion: float) -> str:
    """Translate the current finance controls into plain-language guidance."""

    if risk_aversion <= 4e-7:
        return "This setting is patient. The schedule spreads the order out because market impact matters more than short-term price swings."
    if risk_aversion >= 4e-6:
        return "This setting is urgent. The schedule sells a large chunk early because uncertainty about future prices matters more than impact."
    if first_trade_fraction >= 0.03:
        return "This plan is moderately front-loaded: it starts assertively, then tapers as the position gets smaller."
    return "This plan is relatively even-handed: it avoids a dramatic first trade while still steadily reducing risk."


def build_finance_demo(*, liquidation_days: int, num_trades: int, risk_aversion: float) -> dict:
    """Return a finance demo payload for one set of controls.

    Parameters
    ----------
    liquidation_days:
        Number of days available to liquidate the position.
    num_trades:
        Number of execution slices used inside that horizon.
    risk_aversion:
        Almgren-Chriss lambda. Larger values prioritize reducing uncertainty
        about future prices over minimizing immediate market impact.

    Returns
    -------
    dict
        A JSON-serializable payload with control echoes, headline metrics,
        series for charts, and a short narrative summary for the current setup.

    Notes
    -----
    This builder exposes the closed-form benchmark embedded in the archived
    simulator. It does not run the notebook's actor-critic training loop.
    """

    if not FINANCE_MODULE_PATH.exists():
        return _build_finance_demo_fallback(
            liquidation_days=liquidation_days,
            num_trades=num_trades,
            risk_aversion=risk_aversion,
        )

    try:
        MarketEnvironment = _market_environment_cls()
    except (FileNotFoundError, RuntimeError, AttributeError, OSError):
        return _build_finance_demo_fallback(
            liquidation_days=liquidation_days,
            num_trades=num_trades,
            risk_aversion=risk_aversion,
        )

    env = MarketEnvironment(lqd_time=liquidation_days, num_tr=num_trades, lambd=risk_aversion)
    env.reset(liquid_time=liquidation_days, num_trades=num_trades, lamb=risk_aversion)

    trade_list = env.get_trade_list()
    rounded_trades = _round_trade_list(trade_list)
    remaining = (np.ones(num_trades) * env.total_shares) - np.cumsum(rounded_trades)

    expected_shortfall = float(env.get_AC_expected_shortfall(env.total_shares))
    variance = float(env.get_AC_variance(env.total_shares))
    std_dev = float(np.sqrt(variance))
    utility = float(env.compute_AC_utility(env.total_shares))
    first_trade_fraction = float(rounded_trades[0] / env.total_shares)
    half_life = float(1.0 / env.kappa) if env.kappa and isfinite(1.0 / env.kappa) else None

    frontier_points = []
    for point in np.geomspace(1e-7, 1e-4, 28):
        frontier_env = MarketEnvironment(lqd_time=liquidation_days, num_tr=num_trades, lambd=float(point))
        frontier_env.reset(liquid_time=liquidation_days, num_trades=num_trades, lamb=float(point))
        frontier_points.append(
            {
                "risk_aversion": float(point),
                "expected_shortfall": float(frontier_env.get_AC_expected_shortfall(frontier_env.total_shares)),
                "std_dev": float(np.sqrt(frontier_env.get_AC_variance(frontier_env.total_shares))),
            }
        )

    return {
        "controls": {
            "liquidation_days": liquidation_days,
            "num_trades": num_trades,
            "risk_aversion": risk_aversion,
        },
        "metrics": {
            "shares_total": int(env.total_shares),
            "starting_price": float(env.startingPrice),
            "expected_shortfall": expected_shortfall,
            "std_dev": std_dev,
            "utility": utility,
            "half_life": half_life,
            "first_trade_fraction": first_trade_fraction,
            "average_trade_size": float(np.mean(rounded_trades)),
        },
        "series": {
            "trade_list": [int(value) for value in rounded_trades.tolist()],
            "remaining": [int(max(value, 0)) for value in remaining.tolist()],
            "frontier": frontier_points,
        },
        "story": {
            "headline": "Optimal execution turns a big sale into a timing problem, not just a math problem.",
            "body": _finance_story(first_trade_fraction, risk_aversion),
        },
        "source_mode": "archive",
        "source_note": "Using the archived Almgren-Chriss simulator from source-material/finance/syntheticChrissAlmgren.py.",
    }


FOUNDATION_MAP = (
    "SFFF",
    "FHFH",
    "FFFH",
    "HFFG",
)
ACTION_NAMES = ("Left", "Down", "Right", "Up")
ACTION_ARROWS = ("<-", "v", "->", "^")


def foundations_presets() -> tuple[dict, ...]:
    """Return preset controls for the foundations demo.

    Each preset highlights a different intuition: a balanced default, a highly
    slippery map, or a more short-sighted agent.
    """

    return (
        {
            "label": "Balanced",
            "discount": 0.92,
            "slip": 0.10,
            "living_reward": -0.04,
            "summary": "A sensible mix of patience, danger, and time pressure.",
        },
        {
            "label": "Icy",
            "discount": 0.94,
            "slip": 0.24,
            "living_reward": -0.04,
            "summary": "Movement is unreliable, so the policy gets more cautious around holes.",
        },
        {
            "label": "Short-sighted",
            "discount": 0.72,
            "slip": 0.08,
            "living_reward": -0.02,
            "summary": "Future rewards matter less, so only the nearby path really pulls the agent.",
        },
    )


def _state_index(row: int, col: int, ncol: int) -> int:
    """Encode one grid coordinate into a flat state index."""

    return row * ncol + col


def _decode_state(index: int, ncol: int) -> tuple[int, int]:
    """Decode a flat state index back into ``(row, col)`` form."""

    return divmod(index, ncol)


def _step(row: int, col: int, action: int) -> tuple[int, int]:
    """Apply one intended move with clipping at the grid boundaries."""

    if action == 0:
        col = max(col - 1, 0)
    elif action == 1:
        row = min(row + 1, len(FOUNDATION_MAP) - 1)
    elif action == 2:
        col = min(col + 1, len(FOUNDATION_MAP[0]) - 1)
    else:
        row = max(row - 1, 0)
    return row, col


def _cell_reward(cell: str, living_reward: float) -> tuple[float, bool]:
    """Return the reward and terminal flag for landing on one cell type."""

    if cell == "G":
        return 1.0, True
    if cell == "H":
        return -1.0, True
    return living_reward, False


def _transitions_for_state(row: int, col: int, action: int, slip: float, living_reward: float) -> list[tuple[float, int, float, bool]]:
    """Return transition tuples for one state-action pair in the local gridworld.

    The archived coursework used a Gym-based FrozenLake environment. The web
    demo reimplements only the transition logic it needs so the page remains
    self-contained and easy to run under the current app stack.
    """

    chosen_prob = max(0.0, 1.0 - (2.0 * slip))
    directions = (
        ((action - 1) % 4, slip),
        (action, chosen_prob),
        ((action + 1) % 4, slip),
    )
    transitions: list[tuple[float, int, float, bool]] = []
    for actual_action, probability in directions:
        if probability <= 0.0:
            continue
        next_row, next_col = _step(row, col, actual_action)
        cell = FOUNDATION_MAP[next_row][next_col]
        reward, done = _cell_reward(cell, living_reward)
        transitions.append((probability, _state_index(next_row, next_col, len(FOUNDATION_MAP[0])), reward, done))
    return transitions


def build_foundations_demo(*, discount: float, slip: float, living_reward: float) -> dict:
    """Return a value-iteration payload for the foundations demo.

    Parameters
    ----------
    discount:
        Gamma in the Bellman backup.
    slip:
        Probability mass assigned to each sideways slip direction.
    living_reward:
        Reward or penalty on ordinary non-terminal tiles.

    Returns
    -------
    dict
        A JSON-serializable payload with controls, headline metrics, per-tile
        values, greedy policy hints, a path trace from the start state, and a
        short story describing the current regime.

    Notes
    -----
    This intentionally uses a tiny local gridworld instead of importing the old
    Gym environment. The demo only needs the 4x4 map and slippery dynamics to
    teach the planning idea.
    """

    nrow = len(FOUNDATION_MAP)
    ncol = len(FOUNDATION_MAP[0])
    state_count = nrow * ncol
    values = np.zeros(state_count, dtype=float)
    terminal_values = {"G": 1.0, "H": -1.0}

    def is_terminal(index: int) -> bool:
        row, col = _decode_state(index, ncol)
        return FOUNDATION_MAP[row][col] in terminal_values

    for _ in range(200):
        next_values = values.copy()
        delta = 0.0
        for state in range(state_count):
            row, col = _decode_state(state, ncol)
            cell = FOUNDATION_MAP[row][col]
            if cell in terminal_values:
                next_values[state] = terminal_values[cell]
                continue
            action_values = []
            for action in range(4):
                total = 0.0
                for probability, next_state, reward, done in _transitions_for_state(row, col, action, slip, living_reward):
                    total += probability * (reward + (0.0 if done else discount * values[next_state]))
                action_values.append(total)
            next_values[state] = max(action_values)
            delta = max(delta, abs(next_values[state] - values[state]))
        values = next_values
        if delta < 1e-7:
            break

    grid = []
    policy = []
    path = []
    path_states = [0]
    start_state = 0
    current_state = start_state
    visited = set()
    for _ in range(12):
        if current_state in visited:
            break
        visited.add(current_state)
        row, col = _decode_state(current_state, ncol)
        cell = FOUNDATION_MAP[row][col]
        if cell in {"G", "H"}:
            break
        action_scores = []
        for action in range(4):
            total = 0.0
            for probability, next_state, reward, done in _transitions_for_state(row, col, action, slip, living_reward):
                total += probability * (reward + (0.0 if done else discount * values[next_state]))
            action_scores.append(total)
        best_action = int(np.argmax(action_scores))
        policy.append(best_action)
        next_row, next_col = _step(row, col, best_action)
        current_state = _state_index(next_row, next_col, ncol)
        path.append(ACTION_NAMES[best_action])
        path_states.append(current_state)

    for row in range(nrow):
        for col in range(ncol):
            state = _state_index(row, col, ncol)
            cell = FOUNDATION_MAP[row][col]
            display_value = float(values[state])
            best_action_name = None
            best_action_arrow = None
            if cell not in terminal_values:
                action_scores = []
                for action in range(4):
                    total = 0.0
                    for probability, next_state, reward, done in _transitions_for_state(row, col, action, slip, living_reward):
                        total += probability * (reward + (0.0 if done else discount * values[next_state]))
                    action_scores.append(total)
                best_action = int(np.argmax(action_scores))
                best_action_name = ACTION_NAMES[best_action]
                best_action_arrow = ACTION_ARROWS[best_action]
            grid.append(
                {
                    "index": state,
                    "row": row,
                    "col": col,
                    "cell": cell,
                    "value": round(display_value, 3),
                    "best_action": best_action_name,
                    "best_action_arrow": best_action_arrow,
                }
            )

    best_first_move = ACTION_NAMES[policy[0]] if policy else "Stay put"
    if slip >= 0.2:
        story = "High slip makes danger spread outward. The policy avoids shortcuts near holes because a small mistake can be costly."
    elif discount <= 0.78:
        story = "A lower discount makes the agent short-sighted. Only nearby rewards pull strongly, so long detours look less worthwhile."
    else:
        story = "With moderate slip and a strong discount, the value of the goal propagates backward through the map and shapes a stable route."

    return {
        "controls": {
            "discount": discount,
            "slip": slip,
            "living_reward": living_reward,
        },
        "metrics": {
            "start_value": round(float(values[start_state]), 3),
            "best_first_move": best_first_move,
            "path_length_hint": len(path),
            "safe_tiles": sum(1 for row in FOUNDATION_MAP for cell in row if cell == "F"),
        },
        "grid": grid,
        "path": path,
        "path_states": path_states,
        "story": {
            "headline": "Value iteration pushes the goal backward through the map until each square knows how promising it is.",
            "body": story,
        },
    }
