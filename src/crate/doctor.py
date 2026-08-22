"""`crate doctor`: auth, agent backend, source health, registry schema, cache
status, credits graph, drift."""

from typing import Any

from . import agent, config, fetchers, graph, learning, state


def run_checks(check_sources: bool = True) -> dict[str, Any]:
    report: dict[str, Any] = {"ok": True, "checks": {}}

    initialized = config.sources_path().exists()
    report["checks"]["initialized"] = {
        "ok": initialized,
        "detail": str(config.crate_home()) if initialized else "run `crate init`",
    }

    ok, detail = agent.agent_available()
    report["checks"]["agent_backend"] = {"ok": ok, "detail": detail}

    spotify_ok, spotify_detail = _check_spotify()
    report["checks"]["spotify"] = {"ok": spotify_ok, "detail": spotify_detail}

    if check_sources and initialized:
        report["checks"]["sources"] = _check_sources()

    if initialized:
        report["checks"]["registry_schema"] = _check_registry_schema()

    report["checks"]["graph"] = _check_graph()

    cache = config.cache_dir()
    n_cached = len(list(cache.glob("*.json"))) if cache.exists() else 0
    n_manual = len(list(config.manual_dir().glob("*.md"))) if config.manual_dir().exists() else 0
    report["checks"]["cache"] = {
        "ok": True,
        "detail": f"{n_cached} cached fetches, {n_manual} manual ingests",
    }

    drift = learning.drift_check()
    if drift:
        report["checks"]["drift"] = {"ok": not drift["drifting"], "detail": drift}

    report["ok"] = all(
        c.get("ok", True) for c in report["checks"].values() if isinstance(c, dict)
    )
    return report


def _check_spotify() -> tuple[bool, str]:
    from . import spotify

    if not config.auth_path().exists():
        return False, "not authorized — run `crate init`"
    try:
        user = spotify.me()
        return True, f"authorized as {user.get('display_name') or user.get('id')}"
    except Exception as exc:
        return False, f"auth present but API call failed: {exc}"


def _check_sources() -> dict[str, Any]:
    results = {}
    for source in state.load_sources():
        access = source.get("access", "manual")
        if access in ("manual", "web", "scrape"):
            n = len(fetchers.load_manual_ingests(source["name"], max_items=99))
            results[source["name"]] = f"{access} (agent/manual path; {n} ingests on file)"
            continue
        gathered = fetchers.gather_source_material(source)
        results[source["name"]] = gathered["fetch_status"]
    dead = [k for k, v in results.items() if str(v).startswith("error")]
    return {"ok": not dead, "detail": results, "dead_sources": dead}


def _check_registry_schema() -> dict[str, Any]:
    """Report registry fields that are being defaulted in memory.

    Not a failure — `load_sources` backfills them and digs work fine. It is
    reported because an unwritten prior is an invisible one, and `incentive`
    changes how much a source's vouching counts.
    """
    import yaml

    raw = yaml.safe_load(config.sources_path().read_text()) or {}
    _, filled = state.backfill_source_defaults(raw.get("sources", []))
    if not filled:
        return {"ok": True, "detail": "registry has every current field"}
    return {
        "ok": True,
        "detail": (
            f"{len(filled)} source(s) using a defaulted `incentive` — "
            "run `crate sources migrate` to write the values down and edit them"
        ),
        "defaulted": filled,
    }


def _check_graph() -> dict[str, Any]:
    """Credits-graph size. An empty graph is the expected state before the
    first online dig, so it is never a failure — just worth saying, since a thin
    graph means the lineage leads in SOURCE are thin too."""
    data = graph.stats()
    if not data["edges"]:
        return {"ok": True, "detail": "empty — grows on the first online dig"}
    return {
        "ok": True,
        "detail": (
            f"{data['nodes']} nodes, {data['edges']} edges, "
            f"{int(data['attested_share'] * 100)}% attested"
        ),
    }
