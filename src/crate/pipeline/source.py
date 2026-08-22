"""SOURCE: the agentic core. Pick a rotated, exploration-respecting subset of
the registry, gather deterministic material (feeds, NTS API, manual ingests),
walk the credits graph out from tonight's material and the canon, then hand the
digger playbook to the agent to produce a provenance-attached candidate pool.

The graph pass (P9) supplies *attested facts* - who arranged the record, who
played on it, which label put it out, straight from Discogs - as leads for the
agent to dig. It never supplies candidates itself and never becomes a track's
source: the registry source that started the chain stays the source, and the
traversal path is recorded in `why` (P11)."""

import json
import random
from typing import Any

from .. import agent, config, discogs, fetchers, lineage, state


def pick_sources(
    sources: list[dict[str, Any]],
    signals: dict[str, Any],
    rng: random.Random | None = None,
) -> list[dict[str, Any]]:
    """Weighted pick of 4-7 sources with two hard rules:
    - never the identical set as last run (rotation, §5.4.3)
    - at least ceil(20%) of picks have no feedback history (exploration floor)
    """
    rng = rng or random.Random()
    if not sources:
        return []
    k = min(len(sources), rng.randint(config.SOURCES_PER_RUN_MIN, config.SOURCES_PER_RUN_MAX))
    last_set = set(signals.get("last_source_set", []))

    cold = [s for s in sources if s.get("feedback_count", 0) == 0]
    n_cold_required = min(len(cold), max(1, round(k * config.EXPLORATION_FLOOR)))

    def weighted_sample(pool: list[dict], n: int) -> list[dict]:
        pool = list(pool)
        picked = []
        while pool and len(picked) < n:
            weights = [max(s.get("trust", 0.5), config.SOURCE_WEIGHT_FLOOR) for s in pool]
            choice = rng.choices(pool, weights=weights, k=1)[0]
            picked.append(choice)
            pool.remove(choice)
        return picked

    available_types = len({str(s.get("type", "")) for s in sources if s.get("type")})
    want_types = min(config.MIN_SOURCE_TYPES, available_types, k)

    best = None
    for _ in range(20):  # retry until the set differs from last run
        picked = weighted_sample(cold, n_cold_required)
        rest = [s for s in sources if s not in picked]
        picked += weighted_sample(rest, k - len(picked))
        names = {s["name"] for s in picked}
        if names == last_set and len(sources) > k:
            continue
        # Rotation guarantees a different *set* but says nothing about its
        # shape, so a draw can come back as five reissue labels — wide
        # geographically, narrow structurally, because every source in it finds
        # music the same way. Keep the best-spread draw seen rather than
        # rejecting outright: a thin registry may not be able to do better.
        if best is None or type_spread(picked) > type_spread(best):
            best = picked
        if type_spread(picked) >= want_types:
            return picked
    return best if best is not None else picked


def type_spread(picked: list[dict[str, Any]]) -> int:
    return len({str(s.get("type", "")) for s in picked if s.get("type")})


def gather_material(picked: list[dict[str, Any]]) -> dict[str, Any]:
    material = {}
    for source in picked:
        material[source["name"]] = fetchers.gather_source_material(source)
    return material


def graph_pass(material: dict[str, Any], offline: bool = False) -> dict[str, Any]:
    """Grow the credits graph from tonight's material and return the
    neighborhood as digging leads.

    Never raises: a thin graph makes for a smaller dig, not a failed one - the
    same contract `fetchers.gather_source_material` holds for a dead source.
    Skipped entirely when offline, since every edge here costs a live request.
    """
    if offline:
        return {"leads": [], "summary": {"skipped": "offline"}}
    try:
        seeds = lineage.seed_records(material, limit=config.GRAPH_SEEDS_PER_RUN)
        summary = lineage.build_from_records(seeds, budget=discogs.Budget())
        return {"leads": lineage.neighborhood(seeds), "summary": summary}
    except Exception as exc:
        return {"leads": [], "summary": {"error": str(exc)}}


def run_source_stage(
    run_spec: dict[str, Any],
    dry_run_offline: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Returns (candidates, picked_sources). Each candidate:
    {track, artist, album?, year?, region?, source, source_type, why}."""
    sources = state.load_sources()
    signals = run_spec["signals"]
    picked = pick_sources(sources, signals)
    if not picked:
        raise RuntimeError("No sources in registry. Run `crate init` first.")

    material = gather_material(picked)
    graph_material = graph_pass(material, offline=dry_run_offline)
    exclusions = state.load_exclusions()

    playbook = agent.load_prompt("curator-model")
    prompt = agent.load_prompt(
        "source",
        brief=run_spec["brief"] or "(no brief — curator's choice)",
        mood_prior=run_spec["mood_prior"] or "(none)",
        taste=run_spec["taste"] or "(no taste profile yet — assume an open, curious listener)",
        length=str(run_spec["length"]),
        stretch_budget=str(run_spec["stretch_budget"]),
        pool_min=str(config.CANDIDATE_POOL_MIN),
        pool_max=str(config.CANDIDATE_POOL_MAX),
        sources_json=json.dumps(
            [
                {
                    "name": s["name"],
                    "type": s.get("type", ""),
                    "trust": s.get("trust", 0.5),
                    "notes": s.get("notes", ""),
                    "endpoint": s.get("endpoint", ""),
                }
                for s in picked
            ],
            indent=1,
        ),
        material_json=json.dumps(material, indent=1, default=str)[:60000],
        graph_leads_json=json.dumps(
            graph_material["leads"], indent=1, ensure_ascii=False
        )[:12000],
        exclusions_json=json.dumps(
            {
                "artists": exclusions.get("artists", []),
                "recent_tracks": exclusions.get("used_tracks", [])[-100:],
            }
        ),
    )

    prompt = playbook + "\n\n---\n\n" + prompt
    raw = agent.run_agent_json(prompt, web=not dry_run_offline)
    candidates = raw.get("candidates", raw) if isinstance(raw, dict) else raw
    picked_names = {s["name"] for s in picked}
    all_names = {s["name"] for s in sources}

    cleaned = []
    for c in candidates:
        if not isinstance(c, dict) or not c.get("track") or not c.get("artist"):
            continue
        # Hard requirement: human provenance. A candidate whose claimed source
        # isn't in the registry is dropped.
        src = str(c.get("source", "")).strip()
        if src not in picked_names and src not in all_names:
            continue
        if state.is_excluded(exclusions, c["artist"], c["track"]):
            continue
        # Corroboration may only name sources that are actually in the registry,
        # for the same reason `source` must: an unverifiable second voucher is
        # worth less than none, and cross-source agreement is 25% of the score.
        also = []
        for extra in c.get("also_seen_in") or []:
            name = str(extra.get("source", "") if isinstance(extra, dict) else extra).strip()
            if name in all_names and name != src:
                also.append(extra)
        c["also_seen_in"] = also
        cleaned.append(c)
    if len(cleaned) < run_spec["length"]:
        raise RuntimeError(
            f"SOURCE produced only {len(cleaned)} usable candidates "
            f"(need at least {run_spec['length']}). Check `crate doctor`."
        )
    return cleaned, picked
