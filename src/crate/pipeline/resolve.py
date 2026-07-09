"""RESOLVE: deterministic Spotify catalog matching. Low confidence → drop, and
report the track as an unresolved gem rather than risk the wrong version."""

import urllib.parse
from typing import Any

from .. import config, spotify


def run_resolve_stage(sequenced: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Returns (resolved, unresolved). Resolved tracks gain spotify_uri,
    spotify_match, match_confidence."""
    resolved, unresolved = [], []
    for track in sequenced:
        match = spotify.search_track(
            track["track"], track["artist"], track.get("album") or None
        )
        if match and match["confidence"] >= config.RESOLVE_CONFIDENCE_THRESHOLD:
            track = dict(track)
            track["spotify_uri"] = match["uri"]
            track["spotify_match"] = f"{match['artists']} — {match['name']} ({match['album']})"
            track["match_confidence"] = match["confidence"]
            resolved.append(track)
        else:
            track = dict(track)
            track["best_guess"] = match
            unresolved.append(track)
    # Re-number after drops so the arc stays contiguous.
    for pos, track in enumerate(resolved, start=1):
        track["position"] = pos
    return resolved, unresolved


def unresolved_report(unresolved: list[dict[str, Any]], stamp: str) -> str:
    """The 'you have to find this on Bandcamp' report — often the best digs."""
    lines = [
        f"# Unresolved gems — {stamp}",
        "",
        "Tracks that earned their place but couldn't be confidently matched on",
        "Spotify. These are often the best finds — go get them:",
        "",
    ]
    for t in unresolved:
        q = urllib.parse.quote(f"{t['artist']} {t['track']}")
        lines.append(f"## {t['artist']} — {t['track']}")
        if t.get("album"):
            lines.append(f"*{t['album']}*" + (f" ({t['year']})" if t.get("year") else ""))
        lines.append(f"- Why it belongs: {t.get('conviction', '')}")
        srcs = ", ".join(s["source"] for s in t.get("sources", []))
        lines.append(f"- Provenance: {srcs}")
        if t.get("best_guess"):
            bg = t["best_guess"]
            lines.append(
                f"- Closest Spotify hit (rejected, confidence {bg['confidence']}): "
                f"{bg['artists']} — {bg['name']}"
            )
        lines.append(f"- [Bandcamp search](https://bandcamp.com/search?q={q})")
        lines.append(f"- [YouTube search](https://www.youtube.com/results?search_query={q})")
        lines.append("")
    return "\n".join(lines)
