"""TRIANGULATE: dedupe the pool, have the agent judge fit/stretch/conviction,
then score deterministically and select with the exploration floor enforced.

Judgment is anchored on the canon corpus (P3) rather than made in a vacuum, and
scoring discounts a source's endorsement by its promotional incentive (P4)."""

import collections
import json
import math
import re
import unicodedata
from typing import Any

from .. import agent, canon, config, state


def match_key(artist: str, track: str) -> str:
    """Key for deciding two candidates are the same recording.

    Looser than `state.track_key`, which is exact after lower/strip and is right
    for exclusions — there, a false merge silently bans a track nobody banned.
    Here the risk runs the other way: two sources vouching for the same record
    is the strongest quality signal the scorer has, and it is lost to a tilde or
    a trailing "(Remastered)". Folds diacritics, drops bracketed suffixes and
    punctuation, and ignores a leading article.
    """
    def norm(text: str) -> str:
        text = unicodedata.normalize("NFKD", str(text).strip().lower())
        text = "".join(c for c in text if not unicodedata.combining(c))
        text = re.sub(r"[\(\[].*?[\)\]]", " ", text)
        text = re.sub(r"[^a-z0-9]+", " ", text).strip()
        return re.sub(r"^(the|a|an|le|la|les|el|los) ", "", text)

    return f"{norm(artist)}|{norm(track)}"


def dedupe(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge duplicate entries; independent sources accumulate in `sources` —
    the cross-source signal.

    A candidate may also name sources that corroborate it directly, via
    `also_seen_in`: the SOURCE agent works one source at a time, so without that
    the only corroboration ever detected is an accidental collision between two
    sources' candidate lists.
    """
    merged: dict[str, dict[str, Any]] = {}
    for c in candidates:
        key = match_key(c["artist"], c["track"])
        claimed = [{"source": c.get("source", ""), "why": c.get("why", "")}]
        for extra in c.get("also_seen_in") or []:
            name = str(extra.get("source", "") if isinstance(extra, dict) else extra).strip()
            if name and name != c.get("source"):
                why = extra.get("why", "") if isinstance(extra, dict) else ""
                claimed.append({"source": name, "why": why})
        if key in merged:
            entry = merged[key]
            for claim in claimed:
                if claim["source"] not in [s["source"] for s in entry["sources"]]:
                    entry["sources"].append(claim)
        else:
            entry = dict(c)
            entry["sources"] = claimed
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
    canon_digest = canon.digest()
    prompt = agent.load_prompt(
        "triangulate",
        brief=run_spec["brief"] or "(no brief)",
        taste=run_spec["taste"] or "(no taste profile yet)",
        stretch_budget=str(run_spec["stretch_budget"]),
        canon=canon_digest
        or "(no canon yet — judge against the taste profile alone, and say so "
        "rather than inventing a reference)",
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


def rating_health(judged: list[dict[str, Any]]) -> dict[str, Any]:
    """Is the agent actually discriminating, or rating everything the same?

    Reported rather than silently corrected. A degenerate stretch column means
    the stretch budget is calibrating on noise, and that is worth a human
    knowing about — it is not something the scorer can fix.
    """
    fits = [c.get("fit", 0.5) for c in judged]
    stretches = [c.get("stretch", 0.5) for c in judged]
    n = len(judged) or 1
    top_stretch = max(collections.Counter(stretches).values()) if stretches else 0
    return {
        "n": len(judged),
        "distinct_fit": len(set(fits)),
        "fit_range": round(max(fits) - min(fits), 3) if fits else 0.0,
        "distinct_stretch": len(set(stretches)),
        "stretch_uniformity": round(top_stretch / n, 3),
        "fit_degenerate": len(set(fits)) < config.MIN_DISTINCT_FIT_VALUES,
        "stretch_degenerate": (top_stretch / n) >= config.DEGENERATE_RATING_SHARE,
    }


def fit_ranks(judged: list[dict[str, Any]]) -> dict[int, float]:
    """Map each candidate's index to its fit percentile within this pool.

    `fit` is written as an absolute 0-1 judgement but is only ever used to rank
    one pool against itself, and agents compress absolute ratings hard — an
    observed dig produced four distinct fit values across fifteen tracks, all
    inside 0.75-0.85, which reduces a 25% term to noise. Ranking is immune to
    that: it uses whatever ordering the agent expressed, however narrow the
    numbers. Ties share the midpoint of the span they occupy, so genuinely
    equal candidates stay equal instead of being ordered by list position.
    """
    if not judged:
        return {}
    if len(judged) == 1:
        return {0: 0.5}
    order = sorted(range(len(judged)), key=lambda i: judged[i].get("fit", 0.5))
    ranks: dict[int, float] = {}
    i = 0
    last = len(judged) - 1
    while i < len(order):
        j = i
        value = judged[order[i]].get("fit", 0.5)
        while j + 1 < len(order) and judged[order[j + 1]].get("fit", 0.5) == value:
            j += 1
        shared = ((i + j) / 2) / last
        for k in range(i, j + 1):
            ranks[order[k]] = round(shared, 4)
        i = j + 1
    return ranks


def score(
    candidate: dict[str, Any],
    trust_by_source: dict[str, float],
    budget: float,
    top_track_keys: set[str],
    incentive_by_source: dict[str, float] | None = None,
    fit_value: float | None = None,
) -> float:
    """Deterministic score. `incentive_by_source` discounts a source's *vouching*
    (P4) — not the track. A record on a label the listener would love is not
    worse for being on that label; what is worth less is the label saying so.
    So the penalty multiplies the provenance and cross-source terms, and leaves
    fit and stretch untouched: those come from judging the music itself."""
    incentive_by_source = incentive_by_source or {}
    names = [s["source"] for s in candidate.get("sources", [])]
    trusts = [
        trust_by_source.get(name, 0.3) * incentive_by_source.get(name, 1.0)
        for name in names
    ]
    provenance = max(trusts) if trusts else 0.3
    n_sources = len(candidate.get("sources", []))
    # Cross-source appearance is the strongest quality signal we have — but two
    # promotional sources agreeing is much weaker than two disinterested ones,
    # so the corroboration is discounted by the sources doing the corroborating.
    cross = min(1.0, (n_sources - 1) * 0.6) if n_sources > 1 else 0.0
    if cross and names:
        cross *= sum(incentive_by_source.get(n, 1.0) for n in names) / len(names)
    fit = candidate.get("fit", 0.5) if fit_value is None else fit_value
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
    incentive_by_source: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Top-N by score, with >= EXPLORATION_FLOOR of slots reserved for tracks
    whose provenance includes a source with no feedback history, and no single
    source allowed past MAX_SOURCE_SHARE of the playlist.

    The cap is applied to the general slots only. The exploration reserve is a
    floor that exists to defeat exactly this kind of tidying, so it is filled
    first and is allowed to breach the cap; anything else would let one
    guardrail quietly eat the other.
    """
    top_track_keys = top_track_keys or set()
    budget = run_spec["stretch_budget"]
    n = run_spec["length"]
    ranks = fit_ranks(judged)
    for i, c in enumerate(judged):
        c["score"] = score(
            c, trust_by_source, budget, top_track_keys, incentive_by_source, ranks.get(i)
        )

    ranked = sorted(judged, key=lambda c: c["score"], reverse=True)

    def is_exploration(c: dict[str, Any]) -> bool:
        return any(s["source"] in cold_sources for s in c.get("sources", []))

    n_explore = math.ceil(n * config.EXPLORATION_FLOOR)
    explore_pool = [c for c in ranked if is_exploration(c)]
    reserved = explore_pool[:n_explore]

    max_per_source = max(1, math.floor(n * config.MAX_SOURCE_SHARE))
    used: collections.Counter[str] = collections.Counter()

    def primary(c: dict[str, Any]) -> str:
        """A track's slot is charged to its best-trusted source — the one the
        scorer credited for it."""
        names = [s["source"] for s in c.get("sources", [])]
        if not names:
            return ""
        return max(names, key=lambda nm: trust_by_source.get(nm, 0.3))

    for c in reserved:
        used[primary(c)] += 1

    selection = list(reserved)
    deferred: list[dict[str, Any]] = []
    for c in ranked:
        if len(selection) >= n:
            break
        if c in reserved:
            continue
        name = primary(c)
        if used[name] >= max_per_source:
            deferred.append(c)
            continue
        selection.append(c)
        used[name] += 1

    # Only if the cap could not be honoured — a thin pool, or one source
    # supplying nearly everything — does it yield. A short playlist is worse
    # than a lopsided one.
    for c in deferred:
        if len(selection) >= n:
            break
        selection.append(c)

    return sorted(selection, key=lambda c: c["score"], reverse=True)[:n]


def run_triangulate_stage(
    candidates: list[dict[str, Any]],
    run_spec: dict[str, Any],
    top_track_keys: set[str] | None = None,
) -> list[dict[str, Any]]:
    sources = state.load_sources()
    trust_by_source = {s["name"]: s.get("trust", 0.5) for s in sources}
    incentive_by_source = {s["name"]: config.incentive_factor(s) for s in sources}
    cold = {s["name"] for s in sources if s.get("feedback_count", 0) == 0}
    pool = dedupe(candidates)
    judged = judge_candidates(pool, run_spec)
    if len(judged) < run_spec["length"]:
        raise RuntimeError(
            f"Only {len(judged)} candidates survived triangulation; "
            f"need {run_spec['length']}."
        )
    run_spec["rating_health"] = rating_health(judged)
    run_spec["corroborated"] = sum(1 for c in judged if len(c.get("sources", [])) > 1)
    return select(
        judged, run_spec, trust_by_source, cold, top_track_keys, incentive_by_source
    )
