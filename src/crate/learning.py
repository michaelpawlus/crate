"""The learning loop (§5.2-5.4): tune source trust, stretch budget, and the
taste narrative from feedback — inside guardrails that keep CRATE from
collapsing into a similarity engine.

Update rules:
- Source trust: one pooled delta per source per session — the session's mean
  verdict delta, scaled by a confidence factor that saturates with sample size
  — plus a decay term pulling weights 3% toward neutral (0.5) each session so
  old feedback fades. Floor 0.1, ceiling 1.0.
- High-stretch skips get ~1/3 the negative weight of low-stretch skips: a
  missed surprise on the wrong day is weak evidence (§5.4.2).
- Stretch budget: moves with the trailing success rate of high-stretch tracks,
  clamped to [EXPLORATION_FLOOR, 1.0]. The exploration floor itself is a
  constant in config.py — the loop cannot touch it.
- What counts as "high stretch" is read off the observed distribution rather
  than an absolute cut; see high_stretch_cut().
"""

import difflib
import statistics
from typing import Any

from . import agent, config, state

VERDICT_DELTAS = {"love": 0.08, "like": 0.04, "fine": 0.0, "skip": -0.06, "hate": -0.12}
VERDICT_VALUES = {"love": 1.0, "like": 0.7, "fine": 0.5, "skip": 0.25, "hate": 0.0}
DECAY_TOWARD_NEUTRAL = 0.03
STRETCH_STEP = 0.05
STRETCH_WINDOW = 20

# Below this many judged tracks the observed stretch distribution is too thin
# to read a cut off, and high_stretch_cut() falls back to the absolute constant.
MIN_STRETCH_SAMPLES = 6

# Track count at which one session's trust delta carries half its full weight.
# Ten tracks from a source is better evidence than one, but not ten times
# better; this is the saturation knee.
SESSION_HALF_WEIGHT = 3


def high_stretch_cut(history: list[dict[str, Any]]) -> float:
    """The stretch value at or above which a track counts as a real reach.

    config.HIGH_STRETCH_THRESHOLD is an absolute 0-1 cut, but `stretch` is an
    agent-assigned absolute rating, and agents compress those badly — the same
    pathology config.py documents for `fit`. Across the first 26 judged tracks
    the agent never once proposed a stretch above 0.55, so an absolute 0.6 cut
    matched nothing: `high` was always empty, `len(high) >= 4` was never true,
    and the budget could not move in either direction. The calibrator looked
    like it was running and was in fact inert.

    So read the cut off the observed distribution — the upper tercile — instead
    of asserting one. The constant stays as a ceiling rather than a target:
    0.6 is a reach by anyone's reckoning, so a dig that does use the full range
    never gets rescaled down to look timid.
    """
    values = [float(h["stretch"]) for h in history]
    if len(values) < MIN_STRETCH_SAMPLES or len(set(values)) < 2:
        # No spread is not evidence that everything is a stretch. Falling back
        # keeps a degenerate distribution from marking every track "high" and
        # turning the stretch calibrator into an overall-satisfaction meter.
        return config.HIGH_STRETCH_THRESHOLD
    return min(config.HIGH_STRETCH_THRESHOLD, round(statistics.quantiles(values, n=3)[1], 3))


def apply_feedback(feedback: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply one session's feedback to sources.yaml, taste-signals.json, and
    exclusions.json. Returns a summary of what changed."""
    sources = state.load_sources()
    signals = state.load_signals()
    exclusions = state.load_exclusions()
    by_name = {s["name"]: s for s in sources}
    changes: dict[str, Any] = {"source_weights": {}, "exclusions_added": []}

    track_records = [r for r in feedback if r.get("track_pos") is not None]

    # Record this session's stretches before anything reads them, so the trust
    # discount and the budget calibration are judged against the same cut —
    # including the dig currently under review.
    for rec in track_records:
        signals.setdefault("stretch_history", []).append(
            {
                "stretch": float(rec.get("stretch_score", 0.5) or 0.5),
                "value": VERDICT_VALUES.get(rec.get("verdict", "fine"), 0.5),
            }
        )
    signals["stretch_history"] = signals["stretch_history"][-STRETCH_WINDOW * 3 :]
    cut = high_stretch_cut(signals["stretch_history"])
    changes["high_stretch_cut"] = cut

    # --- Source trust updates ---
    for src in sources:
        old = src.get("trust", 0.5)
        src["trust"] = old + (0.5 - old) * DECAY_TOWARD_NEUTRAL

    # Deltas are pooled per source and applied once, not summed per track.
    # Summing let a single session move a source by its delta times its track
    # count — four loves was +0.32 — which pinned both of the first session's
    # productive sources to SOURCE_WEIGHT_CEIL and left a source scoring 0.90
    # indistinguishable from one scoring 0.74. The ceiling is an anti-convergence
    # guardrail and not the loop's to move (see config.py), so the update is
    # what gets fixed: a session contributes its mean delta, scaled by a
    # confidence factor that saturates with sample size.
    pooled: dict[str, list[float]] = {}
    for rec in track_records:
        verdict = rec.get("verdict", "fine")
        delta = VERDICT_DELTAS.get(verdict, 0.0)
        stretch = float(rec.get("stretch_score", 0.5) or 0.5)
        if verdict == "skip" and stretch >= cut:
            delta *= config.HIGH_STRETCH_SKIP_DISCOUNT
        for name in [s.strip() for s in str(rec.get("source", "")).split(",") if s.strip()]:
            if name in by_name:
                pooled.setdefault(name, []).append(delta)

    for name, deltas in pooled.items():
        src = by_name[name]
        confidence = len(deltas) / (len(deltas) + SESSION_HALF_WEIGHT)
        src["trust"] = min(
            config.SOURCE_WEIGHT_CEIL,
            max(
                config.SOURCE_WEIGHT_FLOOR,
                src.get("trust", 0.5) + statistics.mean(deltas) * confidence,
            ),
        )
        src["feedback_count"] = src.get("feedback_count", 0) + len(deltas)

    for src in sources:
        src["trust"] = round(src["trust"], 3)
    changes["source_weights"] = {s["name"]: s["trust"] for s in sources}

    # --- Stretch calibration ---
    high = [
        h["value"]
        for h in signals["stretch_history"][-STRETCH_WINDOW:]
        if h["stretch"] >= cut
    ]
    old_budget = signals["stretch_budget"]
    if len(high) >= 4:
        success = statistics.mean(high)
        if success >= 0.65:
            signals["stretch_budget"] = min(1.0, old_budget + STRETCH_STEP)
        elif success <= 0.35:
            signals["stretch_budget"] = max(
                config.EXPLORATION_FLOOR, old_budget - STRETCH_STEP
            )
    signals["stretch_budget"] = round(signals["stretch_budget"], 3)
    changes["stretch_budget"] = {"old": old_budget, "new": signals["stretch_budget"]}

    # --- Negative space: hates accumulate as exclusions ---
    for rec in track_records:
        if rec.get("verdict") == "hate":
            key = rec["track"].lower()
            if key not in exclusions["tracks"]:
                exclusions["tracks"].append(key)
                changes["exclusions_added"].append(rec["track"])

    signals["feedback_sessions"] = signals.get("feedback_sessions", 0) + 1
    state.save_sources(sources)
    state.save_signals(signals)
    state.save_exclusions(exclusions)
    return changes


# --- Taste narrative updates (§5.3) ---

def propose_taste_update(feedback: list[dict[str, Any]]) -> tuple[str, str]:
    """Have the agent propose a revised taste.md. Returns (new_text, diff).
    Caller decides whether to accept — the human stays in the loop."""
    import json

    current = state.load_taste()
    prompt = agent.load_prompt(
        "taste-update",
        taste=current,
        feedback_json=json.dumps(feedback, indent=1, ensure_ascii=False),
    )
    new_text = agent.run_agent(prompt).strip() + "\n"
    if new_text.startswith("```"):
        new_text = "\n".join(
            line for line in new_text.splitlines() if not line.startswith("```")
        ).strip() + "\n"
    diff = "\n".join(
        difflib.unified_diff(
            current.splitlines(), new_text.splitlines(),
            fromfile="taste.md (current)", tofile="taste.md (proposed)", lineterm="",
        )
    )
    return new_text, diff


# --- Drift audit (§5.4.4) ---

def diversity_index(records: list[dict[str, Any]]) -> float:
    """Rough diversity of a set of playlist records: unique sources, unique
    artists, and era spread, each normalized against track count."""
    tracks = [t for r in records for t in r.get("tracks", [])]
    if not tracks:
        return 0.0
    n = len(tracks)
    sources = {s["source"] for t in tracks for s in t.get("sources", [])}
    artists = {t["artist"].lower() for t in tracks}
    years = []
    for t in tracks:
        # `year` is when the music was made; `reissue_year` is when a label put
        # it out again. Era spread must read the former or a crate of 1970s
        # reissues scores as a contemporary dig and the drift audit is measuring
        # release schedules instead of range.
        try:
            years.append(int(str(t.get("year") or "")[:4]))
        except ValueError:
            pass
    era_spread = (max(years) - min(years)) / 60 if len(years) >= 2 else 0.3
    return round(
        (len(sources) / n) * 0.4 + (len(artists) / n) * 0.4 + min(1.0, era_spread) * 0.2,
        4,
    )


def drift_check() -> dict[str, Any] | None:
    """Every DRIFT_AUDIT_EVERY playlists, compare recent diversity against the
    first three playlists. Contraction beyond the limit → propose a reset run."""
    paths = state.list_playlist_records()
    if len(paths) < config.DRIFT_AUDIT_EVERY:
        return None
    if len(paths) % config.DRIFT_AUDIT_EVERY != 0:
        return None
    baseline = [state.load_playlist_record(p) for p in paths[:3]]
    recent = [state.load_playlist_record(p) for p in paths[-3:]]
    base_div = diversity_index(baseline)
    recent_div = diversity_index(recent)
    contraction = (base_div - recent_div) / base_div if base_div > 0 else 0.0
    return {
        "baseline_diversity": base_div,
        "recent_diversity": recent_div,
        "contraction": round(contraction, 3),
        "drifting": contraction > config.DRIFT_CONTRACTION_LIMIT,
        "recommendation": (
            "Diversity has contracted more than "
            f"{int(config.DRIFT_CONTRACTION_LIMIT * 100)}%. Run a reset: "
            "`crate dig --brief 'reset run: maximum range, no comfort zone'` "
            "(stretch budget is maxed for reset briefs)."
        )
        if contraction > config.DRIFT_CONTRACTION_LIMIT
        else "Diversity holding steady.",
    }
