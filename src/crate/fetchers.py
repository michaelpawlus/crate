"""Deterministic source fetchers: RSS feeds, the NTS JSON API, reddit JSON,
and the manual-ingest path. Everything is cached aggressively under
~/.crate/cache. The agent's own web research supplements these — fetchers are
accelerators, not the only path in."""

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import feedparser
import httpx

from . import config

USER_AGENT = "crate/0.1 (personal playlist tool; github.com/michaelpawlus/crate)"
# Several feeds (Bandcamp Daily, The Quietus, WFMU) 403 non-browser clients.
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
)


def _cache_path(key: str) -> Path:
    digest = hashlib.sha256(key.encode()).hexdigest()[:24]
    return config.cache_dir() / f"{digest}.json"


def cached_fetch(key: str, fetch_fn, ttl: int = config.CACHE_TTL_SECONDS) -> Any:
    path = _cache_path(key)
    if path.exists():
        blob = json.loads(path.read_text())
        if time.time() - blob["fetched_at"] < ttl:
            return blob["data"]
    data = fetch_fn()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"key": key, "fetched_at": time.time(), "data": data}))
    return data


def _get_json(url: str, ua: str = USER_AGENT) -> Any:
    resp = httpx.get(url, headers={"User-Agent": ua}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return resp.json()


# --- RSS ---

def fetch_rss(url: str, limit: int = 15) -> list[dict[str, str]]:
    def _fetch():
        feed = feedparser.parse(url, agent=BROWSER_UA)
        return [
            {
                "title": e.get("title", ""),
                "link": e.get("link", ""),
                "published": e.get("published", ""),
                "summary": (e.get("summary", "") or "")[:500],
            }
            for e in feed.entries[:limit]
        ]

    return cached_fetch(f"rss:{url}", _fetch)


# --- NTS unofficial JSON API ---

def fetch_nts_show(alias: str, episodes: int = 3) -> list[dict[str, Any]]:
    """Latest episodes of an NTS show with tracklists where published. The
    tracklist endpoint returns ISRC / MusicBrainz ids when NTS has them —
    kept for future exact Spotify matching."""

    def _fetch():
        base = "https://www.nts.live/api/v2"
        listing = _get_json(f"{base}/shows/{alias}/episodes?offset=0&limit={episodes}")
        out = []
        for ep in listing.get("results", []):
            ep_alias = ep.get("episode_alias")
            tracklist = []
            try:
                tl = _get_json(f"{base}/shows/{alias}/episodes/{ep_alias}/tracklist")
                tracklist = [
                    {
                        "artist": t.get("artist", ""),
                        "title": t.get("title", ""),
                        "isrc": t.get("isrc_id"),
                    }
                    for t in tl.get("results", [])
                ]
            except httpx.HTTPError:
                pass
            out.append(
                {
                    "episode": ep.get("name", ep_alias),
                    "date": ep.get("broadcast", ""),
                    "tracklist": tracklist,
                }
            )
        return out

    return cached_fetch(f"nts:{alias}:{episodes}", _fetch)


# --- BBC Sounds open RMS API (6 Music live track segments) ---

def fetch_bbc_segments(service: str = "bbc_6music", limit: int = 30) -> list[dict[str, str]]:
    def _fetch():
        data = _get_json(
            f"https://rms.api.bbc.co.uk/v2/services/{service}/segments/latest?limit={limit}"
        )
        out = []
        for seg in data.get("data", []):
            titles = seg.get("titles", {}) or {}
            out.append(
                {
                    "artist": titles.get("primary", ""),
                    "title": titles.get("secondary", ""),
                    "programme": (seg.get("episode") or {}).get("title", "") if isinstance(seg.get("episode"), dict) else "",
                }
            )
        return [s for s in out if s["artist"] and s["title"]]

    return cached_fetch(f"bbc:{service}:{limit}", _fetch)


# --- reddit JSON (weak signal, triangulation only) ---

def fetch_reddit_top(url: str, limit: int = 25) -> list[dict[str, str]]:
    def _fetch():
        data = _get_json(url)
        posts = data.get("data", {}).get("children", [])[:limit]
        return [
            {"title": p["data"].get("title", ""), "score": p["data"].get("score", 0)}
            for p in posts
        ]

    return cached_fetch(f"reddit:{url}", _fetch)


# --- Manual ingest: the path that always works ---

def ingest_manual(source_name: str, text: str, label: str = "") -> Path:
    """Store a pasted tracklist/list for a source. Kept indefinitely (no TTL);
    the SOURCE stage feeds recent ingests to the agent as primary material."""
    config.manual_dir().mkdir(parents=True, exist_ok=True)
    slug = source_name.lower().replace(" ", "-").replace("/", "-")
    stamp = time.strftime("%Y-%m-%d-%H%M%S")
    path = config.manual_dir() / f"{slug}-{stamp}.md"
    header = f"# Manual ingest — {source_name}\n\n_{label}_\n\n" if label else f"# Manual ingest — {source_name}\n\n"
    path.write_text(header + text.strip() + "\n")
    return path


def load_manual_ingests(source_name: str, max_items: int = 3) -> list[str]:
    slug = source_name.lower().replace(" ", "-").replace("/", "-")
    if not config.manual_dir().exists():
        return []
    paths = sorted(config.manual_dir().glob(f"{slug}-*.md"), reverse=True)[:max_items]
    return [p.read_text() for p in paths]


# --- Dispatcher used by the SOURCE stage ---

def gather_source_material(source: dict[str, Any]) -> dict[str, Any]:
    """Fetch whatever this source can give us deterministically. Returns
    {"material": ..., "fetch_status": "ok"|"empty"|"error: ..."}."""
    name = source["name"]
    access = source.get("access", "manual")
    material: Any = None
    status = "ok"
    try:
        if access == "rss" and source.get("endpoint"):
            material = fetch_rss(source["endpoint"])
        elif access == "api" and name == "NTS":
            material = {
                alias: fetch_nts_show(alias) for alias in source.get("shows", [])[:3]
            }
        elif access == "api" and "rms.api.bbc.co.uk" in source.get("endpoint", ""):
            material = fetch_bbc_segments()
        elif access == "api" and "reddit.com" in source.get("endpoint", ""):
            material = fetch_reddit_top(source["endpoint"])
        manual = load_manual_ingests(name)
        if manual:
            material = {"fetched": material, "manual_ingests": manual} if material else {"manual_ingests": manual}
        if material in (None, [], {}):
            status = "empty"
    except Exception as exc:  # a dead source must never kill a dig
        material = None
        status = f"error: {exc}"
    return {"material": material, "fetch_status": status}
