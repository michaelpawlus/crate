"""TRIANGULATE: dedupe the pool, have the agent judge fit/stretch/conviction,
then score deterministically and select with the exploration floor enforced."""

import json
import math
from typing import Any

from .. import agent, config, state


def dedupe(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge duplicate (artist, track) entries; independent sources accumulate
    in `sources` — the cross-source signal."""
    merged: dict[str, dict[str, Any]] = {}
    for c in candidates:
        key = state.track_key(c["artist"], c["track"])
        if key in merged:
            entry = merged[key]
            if c.get("source") not in [s["source"] for s in entry["sources"]]:
                entry["sources"].append(
                    {"source": c.get("source", ""), "why": c.get("why", "")}
                )
        else:
            entry = dict(c)
            entry["sources"] = [{"source": c.get("source", ""), "why": c.get("why", "")}]
            merged[key] = entry
    return list(merged.values())


def judge_candidates(
    candidates: list[dict[str, Any]], run_spec: dict[str, Any]
) -> list[dict[str, Any]]:
    """One batched agent call: per-track fit (0-1), stretch (0-1), and a
    one-sentence conviction. No conviction sentence → track is out (§4.4)."""
    listing = [
        {
            "id": i,
            "track": c["track"],
            "artist": c["artist"],
            "album": c.get("album", ""),
            "year": c.get("year", ""),
            "region": c.get("region", ""),
            "sources": c["sources"],
        }
        for i, c in enumerate(candidates)
    ]
    prompt = agent.load_prompt(
        "triangulate",
        brief=run_spec["brief"] or "(no brief)",
        taste=run_spec["taste"] or "(no taste profile yet)",
        stretch_budget=str(run_spec["stretch_budget"]),
        candidates_json=json.dumps(listing, indent=1, ensure_ascii=False),
    )
    judgments = agent.run_agent_json(prompt)
    if isinstance(judgments, dict):
        judgments = judgments.get("judgments", [])
    by_id = {j["id"]: j for j in judgments if isinstance(j, dict) and "id" in j}
    judged = []
    for i, c in enumerate(candidates):
        j = by_id.get(i)
        if not j or not str(j.get("conviction", "")).strip():
            continue  # forced articulation: can't say why it belongs → out
        c["fit"] = _clamp(j.get("fit", 0.5))
        c["stretch"] = _clamp(j.get("stretch", 0.5))
        c["conviction"] = str(j["conviction"]).strip()
        judged.append(c)
    return judged


def _clamp(x: Any) -> float:
    try:
        return min(1.0, max(0.0, float(x)))
    except (TypeError, ValueError):
        return 0.5


def stretch_reward(stretch: float, budget: float) -> float:
    """Distance is rewarded up to the budget, then penalized past it."""
    if stretch <= budget:
        return stretch / max(budget, 1e-6)
    return max(0.0, 1.0 - (stretch - budget) / max(1.0 - budget, 1e-6))


def score(
    candidate: dict[str, Any],
    trust_by_source: dict[str, float],
    budget: float,
    top_track_keys: set[str],
) -> float:
    trusts = [
        trust_by_source.get(s["source"], 0.3) for s in candidate.get("sources", [])
    ]
    provenance = max(trusts) if trusts else 0.3
    n_sources = len(candidate.get("sources", []))
    # Cross-source appearance is the strongest quality signal we have.
    cross = min(1.0, (n_sources - 1) * 0.6) if n_sources > 1 else 0.0
    fit = candidate.get("fit", 0.5)
    reward = stretch_reward(candidate.get("stretch", 0.5), budget)
    total = 0.30 * provenance + 0.25 * cross + 0.25 * fit + 0.20 * reward
    if state.track_key(candidate["artist"], candidate["track"]) in top_track_keys:
        total -= 0.25  # already heavy in the user's own rotation
    return round(total, 4)


def select(
    judged: list[dict[str, Any]],
    run_spec: dict[str, Any],
    trust_by_source: dict[str, float],
    cold_sources: set[str],
    top_track_keys: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Top-N by score, with >= EXPLORATION_FLOOR of slots reserved for tracks
    whose provenance includes a source with no feedback history."""
    top_track_keys = top_track_keys or set()
    budget = run_spec["stretch_budget"]
    n = run_spec["length"]
    for c in judged:
        c["score"] = score(c, trust_by_source, budget, top_track_keys)

    ranked = sorted(judged, key=lambda c: c["score"], reverse=True)

    def is_exploration(c: dict[str, Any]) -> bool:
        return any(s["source"] in cold_sources for s in c.get("sources", []))

    n_explore = math.ceil(n * config.EXPLORATION_FLOOR)
    explore_pool = [c for c in ranked if is_exploration(c)]
    reserved = explore_pool[:n_explore]
    remaining = [c for c in ranked if c not in reserved]
    selection = reserved + remaining[: n - len(reserved)]
    return sorted(selection, key=lambda c: c["score"], reverse=True)[:n]


def run_triangulate_stage(
    candidates: list[dict[str, Any]],
    run_spec: dict[str, Any],
    top_track_keys: set[str] | None = None,
) -> list[dict[str, Any]]:
    sources = state.load_sources()
    trust_by_source = {s["name"]: s.get("trust", 0.5) for s in sources}
    cold = {s["name"] for s in sources if s.get("feedback_count", 0) == 0}
    pool = dedupe(candidates)
    judged = judge_candidates(pool, run_spec)
    if len(judged) < run_spec["length"]:
        raise RuntimeError(
            f"Only {len(judged)} candidates survived triangulation; "
            f"need {run_spec['length']}."
        )
    return select(judged, run_spec, trust_by_source, cold, top_track_keys)
