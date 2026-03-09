"""Curated content catalog for the DRL repository."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache


@dataclass(frozen=True, slots=True)
class AssetRef:
    """One notable repository asset."""

    label: str
    kind: str
    path: str
    note: str


@dataclass(frozen=True, slots=True)
class Section:
    """One content arm in the DRL lab."""

    slug: str
    nav_label: str
    eyebrow: str
    title: str
    summary: str
    readiness: str
    runtime: str
    how_it_works: str
    why_reuse: str
    related_slugs: tuple[str, ...]
    needs: tuple[str, ...]
    highlights: tuple[AssetRef, ...]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["highlights"] = [asdict(asset) for asset in self.highlights]
        return payload


def _asset(label: str, kind: str, path: str, note: str) -> AssetRef:
    return AssetRef(label=label, kind=kind, path=path, note=note)


@lru_cache(maxsize=1)
def get_catalog() -> tuple[Section, ...]:
    """Return the curated catalog for the DRL app."""

    return (
        Section(
            slug="foundations",
            nav_label="Foundations",
            eyebrow="Tabular RL + Classic Control",
            title="Foundations and warm-up labs",
            summary="The cleanest path for reviewing how RL pieces fit together before deep networks dominate the picture.",
            readiness="Ready to curate now",
            runtime="Mostly modernizable",
            how_it_works=(
                "This branch is notebook-first. It walks from policy/value iteration into Monte Carlo and "
                "temporal-difference learning, then moves into discretization, tile coding, hill climbing, "
                "cross-entropy, and Taxi. The material is structured as short exercises plus matching solution notebooks."
            ),
            why_reuse=(
                "These notebooks are the best first candidates for live DRL web lessons because they explain the math "
                "cleanly and usually avoid Unity-specific baggage."
            ),
            related_slugs=("value-based", "policy-gradients"),
            needs=(
                "Port old Gym environment IDs to modern Gymnasium/Gym equivalents.",
                "Convert key notebook narratives into smaller web-native walkthroughs.",
                "Keep solution notebooks available, but present exercises first.",
            ),
            highlights=(
                _asset("Dynamic Programming", "notebook set", "source-material/dynamic-programming", "Policy evaluation, improvement, iteration, and value iteration."),
                _asset("Monte Carlo", "notebook set", "source-material/monte-carlo", "Prediction and control notebook pair with plotting helpers."),
                _asset("Temporal Difference", "notebook set", "source-material/temporal-difference", "Sarsa, Q-learning, and expected Sarsa progression."),
                _asset("Tile Coding", "notebook set", "source-material/tile-coding", "Continuous-state discretization bridge into function approximation."),
                _asset("Taxi Lab", "python module", "source-material/taxi", "Self-contained small environment with `agent.py`, `monitor.py`, and `main.py`."),
            ),
        ),
        Section(
            slug="value-based",
            nav_label="Value-Based",
            eyebrow="DQN + Navigation + Lunar variants",
            title="Value-based methods and DQN lineage",
            summary="The strongest bridge from the course tutorials into project work and later experiments.",
            readiness="Good base after curation",
            runtime="Mixed modern + legacy",
            how_it_works=(
                "This branch starts with the main DQN tutorial, extends into the archived Value-based Methods project bundle, "
                "then reaches the Banana Navigation project and your later LunarLander variants like Double DQN and prioritized replay."
            ),
            why_reuse=(
                "It gives you both the clean reference implementation and the messier follow-on experiments that show how you were exploring beyond the coursework."
            ),
            related_slugs=("foundations", "continuous-control", "archive"),
            needs=(
                "Pick one canonical DQN code path for the web app and mark the others as experiments.",
                "Extract or recreate archived `p1_project.zip` weights for demonstrable playback.",
                "Port LunarLander-related code carefully because the experiment branch has unfinished files.",
            ),
            highlights=(
                _asset("Core DQN Tutorial", "notebook set", "source-material/dqn", "Reference DQN notebooks plus `dqn_agent.py` and `model.py`."),
                _asset("Navigation Project", "project bundle", "source-material/classwork/project-reports/p1_navigation", "Banana environment notebooks, report, and reusable DQN project code."),
                _asset("Archived Navigation Weights", "zip archive", "source-material/classwork/project-reports/p1_navigation/p1_project.zip", "Contains `trained_weights.pth` and `benchmark_weights.pth` inside the archive."),
                _asset("Banana Environment", "unity bundle", "source-material/classwork/project-reports/Banana_Windows_x86_64.zip", "Bundled Windows Unity environment for project 1."),
                _asset("Lunar DQN Experiments", "experiment branch", "source-material/lunar/dqn", "Double DQN, prioritized replay, and alternate preprocessing ideas."),
            ),
        ),
        Section(
            slug="policy-gradients",
            nav_label="Policy Gradients",
            eyebrow="REINFORCE + PPO + Actor-Critic theory",
            title="Policy gradients and actor-critic studies",
            summary="The theory-heavy branch that ties together REINFORCE, PPO, A2C/A3C, GAE, and your Pong experiments.",
            readiness="Strong archive; selective live reuse",
            runtime="Legacy Atari stack for some assets",
            how_it_works=(
                "The cleanest pieces are the REINFORCE notebooks and the actor-critic transcripts. Around that, you have several Pong PPO/REINFORCE experiments, "
                "support utilities, and saved policy checkpoints."
            ),
            why_reuse=(
                "This is the best source for explanatory pages about variance reduction, baselines, clipped objectives, and the move from vanilla policy gradients into actor-critic methods."
            ),
            related_slugs=("foundations", "continuous-control", "papers"),
            needs=(
                "Separate clean theory pages from old Pong-specific implementation artifacts.",
                "Decide whether Pong remains archive-only or gets a modern environment replacement.",
                "Use the transcripts and papers as the primary learning surface, not the rougher experiment code.",
            ),
            highlights=(
                _asset("REINFORCE", "notebook set", "source-material/reinforce", "CartPole notebook pair plus additional exploratory notebooks."),
                _asset("Pong PPO / REINFORCE", "experiment branch", "source-material/reinforce/pong-PPO-REINFORCE", "Multiple notebooks, vectorized env utilities, and saved `.policy` checkpoints."),
                _asset("Actor-Critic Transcripts", "subtitle archive", "source-material/classwork/ContinuousControl_Transcripts", "A2C, A3C, GAE, DDPG, and related lecture transcripts."),
                _asset("A2C / PPO / GAE Papers", "paper set", "resources", "Reference PDFs for A2C/A3C, PPO, GAE, and TRPO-style ideas."),
            ),
        ),
        Section(
            slug="continuous-control",
            nav_label="Continuous Control",
            eyebrow="DDPG + Reacher + Unity project work",
            title="Continuous control and the Reacher project",
            summary="The deepest single branch in the repo and the likely centerpiece of the eventual DRL arm.",
            readiness="High-value but legacy-heavy",
            runtime="Requires isolated Unity/ML-Agents stack",
            how_it_works=(
                "This area combines the course DDPG tutorials, multiple Reacher implementations, single-agent and twenty-agent project variants, "
                "vectorized environment experiments, PPO/REINFORCE side paths, sample transition CSVs, and the vendored ML-Agents Python package."
            ),
            why_reuse=(
                "It connects theory, project practice, environment assets, and your own experiments better than any other branch in the archive."
            ),
            related_slugs=("policy-gradients", "multi-agent", "finance"),
            needs=(
                "Containerize or otherwise isolate the old `unityagents 0.4.0` / TensorFlow 1.7 stack.",
                "Curate one DDPG path as canonical and demote the rest to archive or experiments.",
                "Use the CSV transition data and Reacher docs for the first review-oriented web pages before promising live training.",
            ),
            highlights=(
                _asset("Project 2 Root", "project bundle", "source-material/classwork/project-reports/p2_continuous-control", "Main notebooks, data, docs, env zips, and multiple code paths."),
                _asset("Multi-agent DDPG", "python module", "source-material/classwork/project-reports/p2_continuous-control/ddpg", "Core Reacher DDPG agent, model, and training loop."),
                _asset("Single-agent DDPG", "python module", "source-material/classwork/project-reports/p2_continuous-control/ddpg_single_agent", "Simpler Reacher variant for the one-agent environment."),
                _asset("Transition CSVs", "dataset", "source-material/classwork/project-reports/p2_continuous-control/data", "Saved states, actions, rewards, dones, and next-state snapshots."),
                _asset("Reacher Unity Bundles", "unity bundle", "source-material/classwork/project-reports/p2_continuous-control/zips", "Bundled Windows executables for one-agent and twenty-agent Reacher."),
            ),
        ),
        Section(
            slug="multi-agent",
            nav_label="Multi-Agent",
            eyebrow="Tennis + Soccer + MARL lecture material",
            title="Multi-agent RL and collaboration/competition",
            summary="The branch for Tennis, Soccer, and the theory around cooperation, competition, and Markov games.",
            readiness="Great study content, thin runtime assets",
            runtime="Theory-first; missing env bundles in repo",
            how_it_works=(
                "This is mostly notebook and transcript material. The project notebooks show the Tennis/Soccer environments, while the subtitle archive covers motivation, applications, "
                "Markov games, cooperation/competition, and a paper walk-through."
            ),
            why_reuse=(
                "It gives the future DRL arm a true multi-agent sub-tree without forcing phase 2 to solve live environment recovery first."
            ),
            related_slugs=("continuous-control", "papers", "archive"),
            needs=(
                "Treat this as a review-and-theory branch first because the actual Tennis/Soccer binaries are not present here.",
                "Later decide whether to restore the old Unity environments or replace them with a modern multi-agent sandbox.",
                "Cross-link this branch with actor-critic and continuous-control concepts, because the dependencies are conceptual as well as technical.",
            ),
            highlights=(
                _asset("Project 3 Notebooks", "project bundle", "source-material/classwork/project-reports/p3_collaborate-compete", "Tennis and Soccer notebooks plus the project README."),
                _asset("MARL Subtitles", "subtitle archive", "source-material/classwork/Introduction+to+Multi-Agent+RL+Subtitles.zip", "Lecture subtitles for multi-agent foundations and examples."),
            ),
        ),
        Section(
            slug="finance",
            nav_label="Finance",
            eyebrow="Almgren-Chriss execution environment",
            title="Finance as a DRL application branch",
            summary="A rare self-contained domain application in the repo, and one of the most promising early interactive demos.",
            readiness="Best domain-specific live demo candidate",
            runtime="Mostly self-contained Python",
            how_it_works=(
                "The finance notebook and modules model trade execution using the Almgren-Chriss framework. "
                "The code defines a market environment, plotting helpers, and actor/critic networks for optimal execution experiments."
            ),
            why_reuse=(
                "Unlike the Unity branches, this section is domain-specific and mostly self-contained, which makes it ideal for a real web-native DRL application page."
            ),
            related_slugs=("continuous-control", "policy-gradients", "papers"),
            needs=(
                "Verify the notebook against current plotting and scientific Python packages.",
                "Promote the environment and charts into a first-class interactive mini-lab.",
                "Document the state/action semantics clearly, because this branch is less familiar than the course projects.",
            ),
            highlights=(
                _asset("Finance Notebook", "notebook", "source-material/finance/DRL.ipynb", "Main walkthrough for optimal execution with RL framing."),
                _asset("Market Environment", "python module", "source-material/finance/syntheticChrissAlmgren.py", "Custom environment implementing the Almgren-Chriss trade execution model."),
                _asset("Finance Helpers", "python module", "source-material/finance/utils.py", "Plotting, tables, and frontier/utility helpers."),
                _asset("Finance Networks", "python module", "source-material/finance/model.py", "Actor and critic definitions for the finance experiments."),
            ),
        ),
        Section(
            slug="papers",
            nav_label="Papers",
            eyebrow="Reference shelf + transcript layer",
            title="Papers, cheatsheets, and transcript assets",
            summary="The reference shelf that can anchor the educational side of the DRL arm even before everything is runnable again.",
            readiness="Ready immediately",
            runtime="No special runtime",
            how_it_works=(
                "This branch is less about code and more about study support: papers, cheatsheets, PDF notes, and lecture transcripts that explain the algorithms used elsewhere in the repo."
            ),
            why_reuse=(
                "It gives the web app depth. Instead of only showing code, you can tie each section back to the source papers and class explanations that motivated it."
            ),
            related_slugs=("foundations", "policy-gradients", "multi-agent"),
            needs=(
                "Organize the references by algorithm family rather than by the raw filesystem layout.",
                "Add short curator notes so the papers become navigable instead of just dumped links.",
                "Reuse the subtitle archives as text sources for section summaries and glossaries.",
            ),
            highlights=(
                _asset("Research Papers", "pdf shelf", "resources", "DQN, prioritized replay, GAE, PPO, TRPO, Q-Prop, GPS, and continuous-control references."),
                _asset("Course Cheatsheet", "pdf", "source-material/classwork/cheatsheet.pdf", "Compact reinforcement learning reference sheet."),
                _asset("Value Methods Cheatsheet", "pdf", "source-material/classwork/project-reports/Value-based-methods/cheatsheet/cheatsheet.pdf", "Duplicate but still useful packaged reference inside the project bundle."),
                _asset("Continuous Control Transcripts", "transcript set", "source-material/classwork/ContinuousControl_Transcripts", "Raw subtitles extracted into plain-text study assets."),
            ),
        ),
        Section(
            slug="archive",
            nav_label="Archive",
            eyebrow="Rough experiments + dead ends + utility scraps",
            title="Archive and lab-notebook material",
            summary="Useful for your personal review, but not something to treat as production-grade code without curation.",
            readiness="Archive first",
            runtime="Unreliable as-is",
            how_it_works=(
                "This is where the repo becomes a personal notebook: loose utilities, cloned variants, abandoned attempts, policy files, clutter folders, and partially broken experiments."
            ),
            why_reuse=(
                "It still matters because it captures your own reasoning trail and the branches you explored after the coursework. "
                "That is valuable review material, even when the code is not clean enough to power the live app directly."
            ),
            related_slugs=("value-based", "policy-gradients", "continuous-control"),
            needs=(
                "Treat this branch as documented archive content, not as a base for phase 2 features.",
                "Pull only proven ideas upward into the other sections after manual review.",
                "Flag known broken files clearly so the future app does not over-promise runnability.",
            ),
            highlights=(
                _asset("Lunar Branch", "experiment branch", "source-material/lunar", "DQN, DDPG, PPO, and hybrid experiments around LunarLander."),
                _asset("Pong Policies", "model artifacts", "source-material/reinforce/pong-PPO-REINFORCE/data", "Saved `.policy` checkpoints from old Pong runs."),
                _asset("Utility Scratchpad", "python module", "source-material/drl_utils.py", "Small snippets and helper fragments collected outside the main folders."),
                _asset("DDPG Clutter", "experiment branch", "source-material/classwork/project-reports/p2_continuous-control/ddpg/clutter", "Old or abandoned Reacher variants that still record your exploration path."),
            ),
        ),
    )
