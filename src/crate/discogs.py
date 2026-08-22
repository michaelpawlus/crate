"""Discogs — the credits graph.

Probed live 2026-08-20 (see `docs/source-access.md`): unauthenticated
`GET /database/search` and `GET /releases/{id}` both answer 200, and a release's
`extraartists` carries real personnel — `Arranged By`, `Directed By`, `Guitar`,
`Written-by` — even on obscure reissues. That is the edge set P9 traverses, and
MusicBrainz does not have it: recording-level relationships there came back
empty for D'Angelo, Alice Coltrane and Mulatu Astatke.

Rate limit is 25 requests/minute unauthenticated, 60 with a free personal token
in `DISCOGS_TOKEN`. Everything goes through `fetchers.cached_fetch`, so the
throttle below only ever paces cache misses.
"""

import difflib
import os
import re
import time
from typing import Any

import httpx

from . import config, fetchers

API = "https://api.discogs.com"
USER_AGENT = "crate/0.1 +https://github.com/michaelpawlus/crate"

# Unauthenticated ceiling is 25/min. Pace to ~20/min for headroom, since a 429
# here costs the whole traversal.
_MIN_INTERVAL = 3.0
_last_call = 0.0

# Fallback similarity for names that are neither equal nor one leading the
# other — spelling variants, mostly. Deliberately strict: a wrong release does
# not merely waste a seed, it writes wrong edges into a graph later digs reason
# from.
ARTIST_MATCH_THRESHOLD = 0.82


class Budget:
    """Per-dig ceiling on live Discogs calls. Cache hits are free and are not
    counted — only requests that would actually leave the machine."""

    def __init__(self, limit: int = config.GRAPH_REQUEST_BUDGET):
        self.limit = limit
        self.spent = 0

    def take(self) -> bool:
        if self.spent >= self.limit:
            return False
        self.spent += 1
        return True


def _throttle() -> None:
    global _last_call
    wait = _MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    """Cached, throttled GET. Returns None on any HTTP failure — a thin credits
    graph is a smaller dig, never a failed one (same principle as
    `fetchers.gather_source_material`)."""
    params = dict(params or {})
    token = os.environ.get("DISCOGS_TOKEN")
    key = f"discogs:{path}:{sorted(params.items())}"

    def _fetch():
        _throttle()
        headers = {"User-Agent": USER_AGENT}
        if token:
            headers["Authorization"] = f"Discogs token={token}"
        try:
            resp = httpx.get(
                f"{API}{path}", params=params, headers=headers, timeout=30,
                follow_redirects=True,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError:
            return None

    return fetchers.cached_fetch(key, _fetch)


def _norm(s: str) -> str:
    # Discogs disambiguates same-named artists with a trailing number:
    # "Ear (11) - Rumspringa". Strip it, and everything else that is not a
    # letter or digit, before comparing.
    s = re.sub(r"\(\d+\)", " ", str(s).lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _artist_of(result_title: str) -> str:
    """Discogs search results carry a combined `"Artist - Release"` title."""
    head, sep, _ = str(result_title).partition(" - ")
    return head if sep else str(result_title)


def artist_matches(queried: str, result_title: str, threshold: float = ARTIST_MATCH_THRESHOLD) -> bool:
    """Is the artist on this result the artist that was asked for?

    Leading-token containment is the rule that matters, because billing an
    artist with their band is the norm in this corpus: "Hailu Mergia" is the
    right answer for "Hailu Mergia & The Walias Band", as are
    "Mulatu Astatke & His Ethiopian Quintet" and "K. Frimpong & His Cubano
    Fiestas". Requiring the shorter name to *lead* the longer one keeps that
    while still refusing "ear" against "Earth, Wind & Fire" — which plain
    substring matching would wave through.
    """
    a, b = _norm(queried).split(), _norm(_artist_of(result_title)).split()
    if not a or not b:
        return False
    if a == b:
        return True
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    if long_[: len(short)] == short:
        return True
    return difflib.SequenceMatcher(None, " ".join(a), " ".join(b)).ratio() >= threshold


def search_release(
    artist: str, title: str = "", budget: Budget | None = None
) -> dict[str, Any] | None:
    """Best release match for an artist/record, or None.

    The artist on the result has to actually be the artist asked for. Discogs
    search is fuzzy and always answers with *something*: `("ear", "Coil")`
    returns Maveth's "Coils Of The Black Earth" with no indication that it is
    unrelated. Seeding the graph from that would attach death-metal personnel to
    a canon anchor, which is the same failure RESOLVE already refuses — on a
    low-confidence match, drop, never substitute.

    `title` may be a track name. Discogs matches those against *release* titles,
    so a track usually resolves to its album and sometimes not at all; a miss
    here is routine and costs the traversal one seed.
    """
    if budget is not None and not budget.take():
        return None
    query = " ".join(x for x in (artist, title) if x).strip()
    if not query:
        return None
    data = _get("/database/search", {"q": query, "type": "release", "per_page": 5})
    results = (data or {}).get("results") or []
    for result in results:
        if artist_matches(artist, result.get("title", "")):
            return result
    return None


def release(release_id: int | str, budget: Budget | None = None) -> dict[str, Any] | None:
    if budget is not None and not budget.take():
        return None
    return _get(f"/releases/{release_id}")


def credits(release_data: dict[str, Any] | None) -> list[dict[str, str]]:
    """Personnel worth traversing, from a release payload.

    Discogs roles are free text and often bracketed or comma-joined
    (`Arranged By [Arreglos], Directed By [Dirección Musical]`), so a role is
    kept when any configured creative role appears anywhere in it.
    """
    if not release_data:
        return []
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in release_data.get("extraartists") or []:
        name = str(entry.get("name") or "").strip()
        role = str(entry.get("role") or "").strip()
        if not name or not role:
            continue
        if not any(r in role.lower() for r in config.GRAPH_CREATIVE_ROLES):
            continue
        key = (name.lower(), role.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": name, "role": role, "artist_id": str(entry.get("id") or "")})
    return out


def labels(release_data: dict[str, Any] | None) -> list[str]:
    if not release_data:
        return []
    return [str(x.get("name") or "").strip() for x in release_data.get("labels") or [] if x.get("name")]


def artist_releases(
    artist_id: str, limit: int = 8, budget: Budget | None = None
) -> list[dict[str, Any]]:
    """Other records a credited person appears on — the actual hop in
    personnel-hopping. Sorted by Discogs' own `year` so a traversal tends to
    surface a body of work rather than one reissue."""
    if not artist_id:
        return []
    if budget is not None and not budget.take():
        return []
    data = _get(f"/artists/{artist_id}/releases", {"per_page": limit, "sort": "year"})
    return (data or {}).get("releases") or []
