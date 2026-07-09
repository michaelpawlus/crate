"""Feedback capture (§5.1): interactive track-by-track walk, and the quick
free-text mode that survives real life. Both write the same JSONL schema."""

import json
from typing import Any

from . import agent, state

VERDICTS = ["love", "like", "fine", "skip", "hate"]


def _base_record(record: dict[str, Any], track: dict[str, Any]) -> dict[str, Any]:
    sources = ", ".join(s["source"] for s in track.get("sources", []))
    return {
        "playlist": record["stamp"],
        "track_pos": track.get("position"),
        "track": f"{track['artist']} — {track['track']}",
        "source": sources,
        "stretch_score": track.get("stretch", 0.5),
    }


def interactive_session(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Walk the playlist track by track, then whole-playlist questions."""
    import typer
    from rich.console import Console

    console = Console()
    out: list[dict[str, Any]] = []
    console.print(f"\n[bold]Feedback — {record['stamp']}[/bold]: {record['thesis']}\n")
    for track in record["tracks"]:
        console.print(
            f"[bold]{track['position']}. {track['artist']} — {track['track']}[/bold]"
        )
        console.print(f"   [dim]{track.get('conviction', '')}[/dim]")
        verdict = typer.prompt(
            "   verdict (love/like/fine/skip/hate, enter=fine)", default="fine"
        ).strip().lower()
        if verdict not in VERDICTS:
            verdict = "fine"
        note = typer.prompt("   note (optional)", default="").strip()
        rec = _base_record(record, track)
        rec.update({"verdict": verdict, "note": note, "tags": []})
        out.append(rec)

    console.print("\n[bold]Whole-playlist:[/bold]")
    questions = {
        "surprise": "Was anything genuinely surprising? Did the surprise land?",
        "sequencing": "Did the arc work — opening, left turn, landing?",
        "change": "One thing you'd change?",
    }
    playlist_rec: dict[str, Any] = {
        "playlist": record["stamp"],
        "track_pos": None,
        "type": "playlist",
        "verdict": None,
    }
    for key, q in questions.items():
        playlist_rec[key] = typer.prompt(f"   {q}", default="").strip()

    sessions = state.load_signals().get("feedback_sessions", 0)
    from . import config

    if (sessions + 1) % config.META_FEEDBACK_EVERY == 0:
        playlist_rec["meta"] = typer.prompt(
            "   Meta: are these playlists getting more or less surprising? "
            "Better or worse?",
            default="",
        ).strip()
    out.append(playlist_rec)
    return out


def parse_quick(text: str, record: dict[str, Any]) -> list[dict[str, Any]]:
    """Agent-parse free text ('loved 3,7,11; skip 5; too mellow overall') into
    the structured schema, anchored to the actual tracklist."""
    listing = [
        {
            "position": t["position"],
            "track": f"{t['artist']} — {t['track']}",
            "stretch": t.get("stretch", 0.5),
            "sources": [s["source"] for s in t.get("sources", [])],
        }
        for t in record["tracks"]
    ]
    prompt = agent.load_prompt(
        "feedback-parse",
        feedback_text=text,
        playlist_stamp=record["stamp"],
        tracks_json=json.dumps(listing, indent=1, ensure_ascii=False),
    )
    parsed = agent.run_agent_json(prompt)
    if isinstance(parsed, dict):
        parsed = parsed.get("records", [])
    by_pos = {t["position"]: t for t in record["tracks"]}
    out = []
    for rec in parsed:
        if not isinstance(rec, dict):
            continue
        pos = rec.get("track_pos")
        if pos in by_pos:
            base = _base_record(record, by_pos[pos])
            base.update(
                {
                    "verdict": rec.get("verdict") if rec.get("verdict") in VERDICTS else "fine",
                    "note": rec.get("note", ""),
                    "tags": rec.get("tags", []),
                }
            )
            out.append(base)
        else:  # whole-playlist observation
            out.append(
                {
                    "playlist": record["stamp"],
                    "track_pos": None,
                    "type": "playlist",
                    "verdict": None,
                    "note": rec.get("note", ""),
                    "tags": rec.get("tags", []),
                }
            )
    return out
