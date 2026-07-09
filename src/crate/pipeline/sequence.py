"""SEQUENCE: a playlist is an argument. The agent orders the selection as an
arc and writes a per-position rationale plus a one-sentence thesis."""

import json
from typing import Any

from .. import agent


def run_sequence_stage(
    selection: list[dict[str, Any]], run_spec: dict[str, Any]
) -> dict[str, Any]:
    listing = [
        {
            "id": i,
            "track": c["track"],
            "artist": c["artist"],
            "album": c.get("album", ""),
            "year": c.get("year", ""),
            "stretch": c.get("stretch", 0.5),
            "conviction": c.get("conviction", ""),
        }
        for i, c in enumerate(selection)
    ]
    prompt = agent.load_prompt(
        "sequence",
        brief=run_spec["brief"] or "(no brief)",
        sequencing_prefs=json.dumps(run_spec.get("sequencing", {})),
        tracks_json=json.dumps(listing, indent=1, ensure_ascii=False),
    )
    result = agent.run_agent_json(prompt)
    thesis = str(result.get("thesis", "")).strip()
    order = result.get("order", [])

    seen: set[int] = set()
    sequenced: list[dict[str, Any]] = []
    for entry in order:
        idx = entry.get("id")
        if not isinstance(idx, int) or idx in seen or idx >= len(selection):
            continue
        seen.add(idx)
        track = dict(selection[idx])
        track["rationale"] = str(entry.get("rationale", "")).strip()
        sequenced.append(track)
    # Anything the agent dropped or mangled keeps its score order at the end.
    for i, c in enumerate(selection):
        if i not in seen:
            track = dict(c)
            track["rationale"] = "(appended: sequencing output omitted this track)"
            sequenced.append(track)

    for pos, track in enumerate(sequenced, start=1):
        track["position"] = pos
    return {"thesis": thesis or "A dig across trusted ears.", "tracks": sequenced}
