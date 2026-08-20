"""The canon corpus (P3): the references judgment is anchored against.

Questlove's recall came from hearing the same records nine to fifteen times a
week for years; Gioia teaches internalising a solo by singing along until the
phrasing is absorbed. The claim behind this file is that a curator's judgment is
built on deep repeated exposure to a reference set, and that a new record is
evaluated *relative to* that set rather than in a vacuum.

Organised by lineage, not genre — the house rule is no genres, and a lineage is
the more useful unit anyway: it says what a body of music *does* and who it came
from, which is what a candidate can then be measured against.

Starts empty on purpose. A canon seeded with someone else's records would be
exactly the imposed taste CRATE exists to avoid; this one is built by the
listener, and grows from what they love.
"""

from typing import Any

import yaml

from . import config, state


def load() -> list[dict[str, Any]]:
    path = config.canon_path()
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text()) or {}
    return data.get("lineages", []) or []


def save(lineages: list[dict[str, Any]]) -> None:
    path = config.canon_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# CRATE canon — the references judgment is anchored against (P3).\n"
        "# Lineages, not genres. Edit freely; manual edits are authoritative.\n"
        + yaml.safe_dump({"lineages": lineages}, sort_keys=False, allow_unicode=True)
    )


def find(name: str) -> dict[str, Any] | None:
    for lin in load():
        if lin.get("name", "").lower() == name.lower():
            return lin
    return None


def add_lineage(name: str, what_it_does: str = "") -> dict[str, Any]:
    lineages = load()
    existing = next((x for x in lineages if x.get("name", "").lower() == name.lower()), None)
    if existing:
        if what_it_does:
            existing["what_it_does"] = what_it_does
        save(lineages)
        return existing
    entry = {
        "name": name,
        "what_it_does": what_it_does,
        "anchors": [],
        "added": state.today_stamp(),
        "last_referenced": state.today_stamp(),
    }
    lineages.append(entry)
    save(lineages)
    return entry


def add_anchor(lineage: str, artist: str, track: str, note: str = "") -> dict[str, Any]:
    """Add a reference record. Creates the lineage if it does not exist yet —
    adding a record you love should never be blocked on naming a category first.
    """
    lineages = load()
    entry = next((x for x in lineages if x.get("name", "").lower() == lineage.lower()), None)
    if entry is None:
        add_lineage(lineage)
        lineages = load()
        entry = next(x for x in lineages if x.get("name", "").lower() == lineage.lower())
    entry.setdefault("anchors", [])
    key = f"{artist.strip()} — {track.strip()}"
    if not any(a.get("record", "").lower() == key.lower() for a in entry["anchors"]):
        entry["anchors"].append({"record": key, "note": note})
    entry["last_referenced"] = state.today_stamp()
    save(lineages)
    return entry


def anchors() -> list[dict[str, str]]:
    """Every anchor record, flattened, for traversal seeding."""
    out = []
    for lin in load():
        for anchor in lin.get("anchors", []) or []:
            record = str(anchor.get("record", ""))
            artist, _, track = record.partition(" — ")
            if artist:
                out.append({"artist": artist.strip(), "track": track.strip(),
                            "lineage": lin.get("name", ""), "note": anchor.get("note", "")})
    return out


def digest(max_lineages: int = 12) -> str:
    """The canon as prompt material: what the listener's ear is calibrated on.
    Empty string when there is no canon yet, so callers can omit the section
    rather than paste a placeholder into the prompt."""
    lineages = load()[:max_lineages]
    if not lineages:
        return ""
    lines = []
    for lin in lineages:
        head = f"- **{lin.get('name','')}**"
        if lin.get("what_it_does"):
            head += f" — {lin['what_it_does']}"
        lines.append(head)
        for anchor in (lin.get("anchors") or [])[:8]:
            note = f" ({anchor['note']})" if anchor.get("note") else ""
            lines.append(f"    - {anchor.get('record','')}{note}")
    return "\n".join(lines)


def touch(names: list[str]) -> None:
    """Mark lineages as referenced. Feeds the decay question the spec leaves
    open (Part VI.5) — a canon that only ever grows stops meaning anything, so
    the data for retiring an entry is collected from the start."""
    if not names:
        return
    lowered = {n.lower() for n in names}
    lineages = load()
    changed = False
    for lin in lineages:
        if lin.get("name", "").lower() in lowered:
            lin["last_referenced"] = state.today_stamp()
            changed = True
    if changed:
        save(lineages)
