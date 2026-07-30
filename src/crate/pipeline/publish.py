"""PUBLISH: create the Spotify playlist, write the liner-notes companion, and
log the playlist record that makes feedback interpretable later."""

import os
import shutil
from pathlib import Path
from typing import Any

from .. import spotify, state


def liner_notes(record: dict[str, Any]) -> str:
    lines = [
        f"# CRATE — {record['stamp']}",
        "",
        f"**Thesis:** {record['thesis']}",
        "",
    ]
    if record.get("brief"):
        lines += [f"**Brief:** {record['brief']}", ""]
    lines += [f"**Sources dug:** {', '.join(record['source_set'])}", "", "---", ""]
    for t in record["tracks"]:
        year = f" ({t['year']})" if t.get("year") else ""
        lines.append(f"## {t['position']}. {t['artist']} — {t['track']}{year}")
        if t.get("album"):
            lines.append(f"*{t['album']}*")
        lines.append(f"- **Why it belongs:** {t.get('conviction', '')}")
        lines.append(f"- **Place in the arc:** {t.get('rationale', '')}")
        for s in t.get("sources", []):
            why = f" — {s['why']}" if s.get("why") else ""
            lines.append(f"- **Dug via:** {s['source']}{why}")
        if t.get("stretch") is not None:
            lines.append(f"- Stretch: {t['stretch']:.2f} · Score: {t.get('score', 0):.2f}")
        lines.append("")
    if record.get("unresolved_count"):
        lines.append(
            f"_{record['unresolved_count']} unresolved gem(s) — see "
            f"{record['stamp']}-unresolved.md_"
        )
    return "\n".join(lines)


def run_publish_stage(
    run_spec: dict[str, Any],
    sequenced: dict[str, Any],
    resolved: list[dict[str, Any]],
    unresolved: list[dict[str, Any]],
    source_set: list[str],
    dry_run: bool,
) -> dict[str, Any]:
    stamp = run_spec["stamp"]
    thesis = sequenced["thesis"]

    playlist_url = None
    playlist_id = None
    if not dry_run and resolved:
        name = f"CRATE · {stamp}"
        playlist = spotify.create_playlist(name, thesis, public=False)
        playlist_id = playlist["id"]
        playlist_url = playlist.get("external_urls", {}).get("spotify")
        spotify.add_tracks(playlist_id, [t["spotify_uri"] for t in resolved])

    tracks = resolved if not dry_run else sequenced["tracks"]
    record = {
        "stamp": stamp,
        "brief": run_spec["brief"],
        "thesis": thesis,
        "dry_run": dry_run,
        "source_set": source_set,
        "playlist_id": playlist_id,
        "playlist_url": playlist_url,
        "stretch_budget": run_spec["stretch_budget"],
        "tracks": tracks,
        "unresolved": unresolved,
        "unresolved_count": len(unresolved),
    }
    state.write_playlist_record(stamp, record)

    notes = liner_notes(record)
    notes_path = state.write_history_file(stamp, "liner-notes.md", notes)
    _mirror_to_obsidian(notes_path)

    if run_spec.get("brief"):
        state.write_history_file(stamp, "brief.md", run_spec["brief"] + "\n")

    if unresolved:
        from .resolve import unresolved_report

        state.write_history_file(stamp, "unresolved.md", unresolved_report(unresolved, stamp))

    # Used tracks join the freshness exclusions.
    exclusions = state.load_exclusions()
    for t in tracks:
        key = state.track_key(t["artist"], t["track"])
        if key not in exclusions["used_tracks"]:
            exclusions["used_tracks"].append(key)
    state.save_exclusions(exclusions)

    signals = state.load_signals()
    signals["last_source_set"] = source_set
    signals["playlists_generated"] = signals.get("playlists_generated", 0) + 1
    state.save_signals(signals)

    record["liner_notes_path"] = str(notes_path)
    return record


def promote_dry_run(record: dict[str, Any]) -> dict[str, Any]:
    """Publish an already-dug dry-run record to Spotify without re-digging.

    RESOLVE only needs `track`, `artist` and optionally `album`, all of which a
    dry-run record already stores — so the expensive agent stages (SOURCE,
    TRIANGULATE, SEQUENCE) never have to run again. Re-digging would not even
    reproduce the list: pick_sources deliberately refuses a source set identical
    to the previous run, and the agent stages are non-deterministic.

    Deliberately does NOT touch signals or exclusions. The original dig already
    appended these tracks to used_tracks, set last_source_set, and incremented
    playlists_generated; redoing that here would double-count and skew the
    drift-audit and meta-feedback cadences, which key off those counters.
    """
    from .resolve import run_resolve_stage, unresolved_report

    stamp = record["stamp"]
    resolved, unresolved = run_resolve_stage(record["tracks"])
    if not resolved:
        raise RuntimeError(
            f"No tracks from {stamp} could be confidently matched on Spotify. "
            f"See {stamp}-unresolved.md."
        )

    name = f"CRATE · {stamp}"
    playlist = spotify.create_playlist(name, record["thesis"], public=False)
    spotify.add_tracks(playlist["id"], [t["spotify_uri"] for t in resolved])

    record = dict(record)
    record["tracks"] = resolved
    record["unresolved"] = unresolved
    record["unresolved_count"] = len(unresolved)
    record["playlist_id"] = playlist["id"]
    record["playlist_url"] = playlist.get("external_urls", {}).get("spotify")
    record["dry_run"] = False
    state.write_playlist_record(stamp, record)

    notes_path = state.write_history_file(stamp, "liner-notes.md", liner_notes(record))
    _mirror_to_obsidian(notes_path)
    if unresolved:
        state.write_history_file(stamp, "unresolved.md", unresolved_report(unresolved, stamp))

    record["liner_notes_path"] = str(notes_path)
    return record


def _mirror_to_obsidian(notes_path: Path) -> None:
    vault = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault or not Path(vault).is_dir():
        return
    dest = Path(vault) / "crate"
    dest.mkdir(exist_ok=True)
    shutil.copy2(notes_path, dest / notes_path.name)
