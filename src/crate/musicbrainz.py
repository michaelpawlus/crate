"""MusicBrainz — identity and release awareness.

Deliberately *not* the credits graph: probed 2026-08-20, recording-level
relationships are empty even for canonical records (see `docs/source-access.md`
and `discogs.py`). What MusicBrainz is good for here is knowing what exists —
clean label catalogs, and the ISRC bridge from a DJ's tracklist into a stable
identity. NTS tracklists already carry per-track ISRCs.

Rate limit is 1 request/second with a descriptive User-Agent. A 503 means "busy,
retry later", not dead — MusicBrainz sheds load under pressure and answered one
of the probe requests that way.
"""

import time
from typing import Any

import httpx

from . import fetchers

API = "https://musicbrainz.org/ws/2"
USER_AGENT = "crate/0.1 (personal playlist tool; github.com/michaelpawlus/crate)"

_MIN_INTERVAL = 1.1
_last_call = 0.0


def _throttle() -> None:
    global _last_call
    wait = _MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def _get(path: str, params: dict[str, Any]) -> Any:
    params = {**params, "fmt": "json"}
    key = f"mb:{path}:{sorted(params.items())}"

    def _fetch():
        _throttle()
        try:
            resp = httpx.get(
                f"{API}{path}", params=params,
                headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError:
            return None

    return fetchers.cached_fetch(key, _fetch)


def releases_by_label(label: str, limit: int = 25) -> list[dict[str, str]]:
    """What a label has actually put out — release awareness decoupled from any
    opinion about it (P8)."""
    data = _get("/release", {"query": f'label:"{label}"', "limit": limit})
    out = []
    for rel in (data or {}).get("releases") or []:
        credit = rel.get("artist-credit") or []
        out.append(
            {
                "title": str(rel.get("title") or ""),
                "artist": str(credit[0].get("name") or "") if credit else "",
                "date": str(rel.get("date") or ""),
                "mbid": str(rel.get("id") or ""),
            }
        )
    return [r for r in out if r["title"]]


def recording_by_isrc(isrc: str) -> dict[str, str] | None:
    """Resolve an ISRC (as NTS supplies) to a stable recording identity."""
    data = _get(f"/isrc/{isrc}", {"inc": "artist-credits"})
    recordings = (data or {}).get("recordings") or []
    if not recordings:
        return None
    rec = recordings[0]
    credit = rec.get("artist-credit") or []
    return {
        "mbid": str(rec.get("id") or ""),
        "title": str(rec.get("title") or ""),
        "artist": str(credit[0].get("name") or "") if credit else "",
    }
