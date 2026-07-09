"""`crate doctor`: auth, agent backend, source health, cache status, drift."""

from typing import Any

from . import agent, config, fetchers, learning, state


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
