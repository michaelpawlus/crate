"""SEQUENCE: a playlist is an argument. The agent orders the selection as an
arc and writes a per-position rationale plus a one-sentence thesis.

This stage reorders an already-selected set, so it must never be able to lose a
dig. If the agent call fails outright the tracks still stand on their own
merits: they fall back to score order and say so, rather than discarding the
SOURCE pool, the graph traversal and the triangulation that produced them."""

import json
from typing import Any

from .. import agent

FALLBACK_THESIS = (
    "A dig across trusted ears — presented in score order, because the "
    "sequencing pass failed."
)


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
    try:
        result = agent.run_agent_json(prompt)
    except agent.AgentError as exc:
        # Degrade, do not abort. Everything upstream of here — the candidate
        # pool, the credits traversal, the judging — is expensive and already
        # done, and each track has a conviction that stands without an arc.
        result = {"thesis": "", "order": [], "sequencing_error": str(exc)}
    sequencing_error = result.get("sequencing_error")
    thesis = str(result.get("thesis", "")).strip()
    order = result.get("order", []) if not sequencing_error else []

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
    missing_note = (
        "(score order: the sequencing pass failed)"
        if sequencing_error
        else "(appended: sequencing output omitted this track)"
    )
    for i, c in enumerate(selection):
        if i not in seen:
            track = dict(c)
            track["rationale"] = missing_note
            sequenced.append(track)

    for pos, track in enumerate(sequenced, start=1):
        track["position"] = pos
    out = {
        "thesis": thesis or (FALLBACK_THESIS if sequencing_error else "A dig across trusted ears."),
        "tracks": sequenced,
    }
    if sequencing_error:
        out["sequencing_error"] = sequencing_error
    return out
