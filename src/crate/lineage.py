"""Building the graph from real credits, and turning a neighborhood into
material the SOURCE stage can dig through.

The division of labour matters. The **facts** come from Discogs — who arranged
it, who played on it, which label put it out. The **candidates** still come from
the agent, which knows the catalogue. That keeps personnel names attested rather
than invented, while leaving the digging to the thing that can dig.

Provenance is unchanged and non-negotiable: a traversal never becomes a track's
source. The registry source that started the chain stays the source, and the
path is recorded in `why` (P11).
"""

from typing import Any

from . import canon, config, discogs, graph, state


def seed_records(material: dict[str, Any], limit: int) -> list[dict[str, str]]:
    """Records to walk out from: canon anchors first (P3 — judgment is anchored
    on internalised references), then what this run's trusted sources actually
    played, then previously loved tracks.

    Canon leads because it is the stable part of the listener's world; the
    fetched material is what is live tonight.
    """
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def push(artist: str, track: str, origin: str) -> None:
        artist, track = str(artist or "").strip(), str(track or "").strip()
        if not artist:
            return
        key = (artist.lower(), track.lower())
        if key in seen:
            return
        seen.add(key)
        out.append({"artist": artist, "track": track, "origin": origin})

    for entry in canon.anchors():
        push(entry["artist"], entry["track"], f"canon:{entry['lineage']}")

    for source_name, gathered in (material or {}).items():
        for artist, track in _tracks_in(gathered):
            push(artist, track, source_name)

    for rec in _loved_tracks():
        push(rec[0], rec[1], "loved")

    return out[:limit]


def _tracks_in(gathered: Any) -> list[tuple[str, str]]:
    """Pull (artist, title) pairs out of whatever a fetcher returned. Shapes
    differ per source, so this walks the structure rather than assuming one."""
    found: list[tuple[str, str]] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            artist = node.get("artist")
            title = node.get("title") or node.get("track")
            if artist and title:
                found.append((str(artist), str(title)))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(gathered)
    return found


def _loved_tracks() -> list[tuple[str, str]]:
    out = []
    for rec in state.load_all_feedback():
        if rec.get("verdict") != "love":
            continue
        label = str(rec.get("track", ""))
        if " — " in label:
            artist, _, track = label.partition(" — ")
            out.append((artist, track))
    return out


def build_from_records(
    records: list[dict[str, str]], budget: discogs.Budget | None = None
) -> dict[str, Any]:
    """Look each record up on Discogs and record what it credits. Returns a
    summary; the edges are persisted."""
    budget = budget or discogs.Budget()
    new_nodes: list[dict[str, Any]] = []
    new_edges: list[dict[str, Any]] = []
    resolved = 0

    for rec in records:
        hit = discogs.search_release(rec["artist"], rec.get("track", ""), budget=budget)
        if not hit or not hit.get("id"):
            continue
        detail = discogs.release(hit["id"], budget=budget)
        if not detail:
            continue
        resolved += 1

        release_name = str(detail.get("title") or hit.get("title") or "")
        release_node = graph.node_id("release", f"{release_name}-{detail.get('id')}")
        new_nodes.append({"id": release_node, "kind": "release", "name": release_name,
                          "meta": {"discogs_id": detail.get("id"), "year": detail.get("year")}})

        artist_node = graph.node_id("artist", rec["artist"])
        new_nodes.append({"id": artist_node, "kind": "artist", "name": rec["artist"]})
        new_edges.append({"src": artist_node, "dst": release_node, "kind": "played-on",
                          "asserted_by": f"discogs:release/{detail.get('id')}", "confidence": 0.9})

        for label_name in discogs.labels(detail):
            label_node = graph.node_id("label", label_name)
            new_nodes.append({"id": label_node, "kind": "label", "name": label_name})
            new_edges.append({"src": release_node, "dst": label_node, "kind": "released-on",
                              "asserted_by": f"discogs:release/{detail.get('id')}", "confidence": 0.95})

        for credit in discogs.credits(detail):
            # Same namespace as the seed artist above, deliberately: see
            # graph.NODE_KINDS. A self-credit then collapses into the node the
            # walk already started from instead of surfacing as a lead.
            person_node = graph.node_id("artist", credit["name"])
            new_nodes.append({"id": person_node, "kind": "artist", "name": credit["name"],
                              "meta": {"discogs_artist_id": credit.get("artist_id", "")}})
            new_edges.append({"src": person_node, "dst": release_node,
                              "kind": _edge_kind_for(credit["role"]), "role": credit["role"],
                              "asserted_by": f"discogs:release/{detail.get('id')}", "confidence": 0.9})

    added_nodes = graph.add_nodes(new_nodes)
    added_edges = graph.add_edges(new_edges)
    return {
        "records_seen": len(records),
        "records_resolved": resolved,
        "nodes_added": added_nodes,
        "edges_added": added_edges,
        "requests_spent": budget.spent,
    }


def _edge_kind_for(role: str) -> str:
    role = role.lower()
    if "produc" in role:
        return "produced"
    if "arrang" in role or "direct" in role or "conduct" in role:
        return "arranged"
    if "written" in role or "compos" in role:
        return "written-by"
    return "played-on"


def neighborhood(seeds: list[dict[str, str]], limit: int = 40) -> list[dict[str, Any]]:
    """The graph material handed to the SOURCE agent: people and labels one or
    two hops out from tonight's seeds, each with the path that reached it and
    who attested it. These are leads to dig, not candidates — the agent still
    has to find the music and say why it belongs."""
    nodes = graph.load_nodes()
    seed_ids = [graph.node_id("artist", s["artist"]) for s in seeds]
    seed_ids = [sid for sid in seed_ids if sid in nodes]
    hops = graph.walk(seed_ids, max_hops=config.GRAPH_MAX_HOPS, limit=limit * 2)

    out = []
    seen_names = {s["artist"].lower() for s in seeds}
    for hop in hops:
        if hop["kind"] not in ("artist", "label"):
            continue
        # A lead back to a seed is not a lead. Kinds were unified so most of
        # these collapse in the walk itself; this catches the rest (an alias, a
        # seed reached two hops out through someone else's record).
        if hop["name"].lower() in seen_names:
            continue
        seen_names.add(hop["name"].lower())
        out.append(
            {
                "name": hop["name"],
                "kind": hop["kind"],
                "connected_via": hop["via"],
                "path": graph.path_phrase(hop, nodes),
                "attested_by": hop["asserted_by"],
            }
        )
        if len(out) >= limit:
            break
    return out
