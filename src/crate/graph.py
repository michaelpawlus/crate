"""The music graph (P9/P10/P13): who played on what, who released it, which
scene it belongs to.

Stored as two JSONL files under `~/.crate/graph/` rather than a database. That
is a deliberate cost: the house rule is that all state is human-readable and
hand-editable, and it is load-bearing for a tool whose premise is that a human
stays in the loop. A graph you cannot `grep` is a graph you cannot argue with.

Every edge records **who asserted it**. A Discogs-attested credit and an
agent's claim about a lineage are both useful and must never be confused, so
`asserted_by` and `confidence` travel with the edge and are surfaced whenever
the graph is used as evidence.
"""

import hashlib
import json
import re
import unicodedata
from typing import Any

from . import config, state

# Edge kinds. The first group is attested (someone published it); the second is
# interpretive (someone argued it). Keep them distinguishable.
ATTESTED_EDGES = ("produced", "played-on", "arranged", "written-by", "released-on", "reissued-by")
INTERPRETIVE_EDGES = ("sample-of", "cover-of", "scene-member", "descendant-of", "mentored-by")
EDGE_KINDS = ATTESTED_EDGES + INTERPRETIVE_EDGES

# One namespace for humans. A credited arranger and a performing artist are the
# same person, and splitting them would make every seed reappear as a lead to
# its own record — and would hide the fact that the drummer on one record is the
# bandleader on another, which is the whole point of traversing credits.
NODE_KINDS = ("artist", "label", "release", "scene", "track")


def nodes_path():
    return config.graph_dir() / "nodes.jsonl"


def edges_path():
    return config.graph_dir() / "edges.jsonl"


def node_id(kind: str, name: str) -> str:
    """Stable id for a node.

    Diacritics are folded first: this registry is built on global music, and
    `Antonio Pinana Hijo` and `Antonio Piñana Hijo` are one person. Without
    folding they slugify to `pinana` and `pi-ana` and the graph quietly holds two
    of everyone.

    A name in a script that folds away entirely (Amharic, Japanese, Cyrillic)
    falls back to a hash of the original rather than an empty id, so those
    artists get a node like everyone else instead of silently vanishing. Same
    for a name that is all punctuation - `!!!` is a band.
    """
    name = str(name).strip()
    if not name:
        return ""
    folded = unicodedata.normalize("NFKD", name.lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")
    if not slug:
        slug = "x" + hashlib.sha256(name.encode()).hexdigest()[:12]
    return f"{kind}:{slug}"


def _read(path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a hand-edited file may have a bad line; skip, don't die
    return out


def load_nodes() -> dict[str, dict[str, Any]]:
    return {n["id"]: n for n in _read(nodes_path()) if n.get("id")}


def load_edges() -> list[dict[str, Any]]:
    return [e for e in _read(edges_path()) if e.get("src") and e.get("dst")]


def _append(path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def add_nodes(new: list[dict[str, Any]]) -> int:
    """Append nodes that aren't already stored. Returns how many were added."""
    known = load_nodes()
    rows = []
    for n in new:
        nid = n.get("id") or node_id(n.get("kind", "artist"), n.get("name", ""))
        if not nid or nid in known:
            continue
        known[nid] = n
        # `today_stamp()` not `now_iso()`: local civil date, matching the rest
        # of the codebase (see the timezone note in CLAUDE.md).
        rows.append({"id": nid, "kind": n.get("kind", "artist"), "name": n.get("name", ""),
                     "first_seen": state.today_stamp(), "meta": n.get("meta", {})})
    _append(nodes_path(), rows)
    return len(rows)


def add_edges(new: list[dict[str, Any]]) -> int:
    """Append edges not already present. Identity is (src, dst, kind) — the same
    credit attested by two different releases is one edge, not two."""
    known = {(e["src"], e["dst"], e.get("kind", "")) for e in load_edges()}
    rows = []
    for e in new:
        key = (e.get("src", ""), e.get("dst", ""), e.get("kind", ""))
        if not key[0] or not key[1] or key in known:
            continue
        known.add(key)
        rows.append(
            {
                "src": key[0], "dst": key[1], "kind": key[2],
                "role": e.get("role", ""),
                "asserted_by": e.get("asserted_by", "unknown"),
                "confidence": float(e.get("confidence", 0.5)),
                "added": state.today_stamp(),
            }
        )
    _append(edges_path(), rows)
    return len(rows)


def neighbors(
    nid: str, kinds: tuple[str, ...] | None = None, edges: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """Edges touching a node, in either direction. Direction is preserved in the
    returned edge; traversal here is deliberately undirected because a credit
    reads both ways — the arranger leads you to the record and back out again."""
    edges = load_edges() if edges is None else edges
    out = []
    for e in edges:
        if kinds and e.get("kind") not in kinds:
            continue
        if e["src"] == nid or e["dst"] == nid:
            out.append(e)
    return out


def walk(
    seeds: list[str], max_hops: int = config.GRAPH_MAX_HOPS, limit: int = 60
) -> list[dict[str, Any]]:
    """Breadth-first walk out from seed nodes. Returns reached nodes with the
    path that reached them — the path is the point (P11: how a track was found
    is part of what it means), so it is carried, not discarded."""
    edges = load_edges()
    nodes = load_nodes()
    seen = set(seeds)
    frontier = [(s, [s]) for s in seeds if s]
    reached: list[dict[str, Any]] = []
    for _ in range(max_hops):
        nxt = []
        for nid, path in frontier:
            for e in neighbors(nid, edges=edges):
                other = e["dst"] if e["src"] == nid else e["src"]
                if other in seen:
                    continue
                seen.add(other)
                hop = {
                    "id": other,
                    "name": (nodes.get(other) or {}).get("name", other),
                    "kind": (nodes.get(other) or {}).get("kind", ""),
                    "via": e.get("role") or e.get("kind", ""),
                    "asserted_by": e.get("asserted_by", ""),
                    "path": [*path, other],
                }
                reached.append(hop)
                nxt.append((other, hop["path"]))
                if len(reached) >= limit:
                    return reached
        frontier = nxt
        if not frontier:
            break
    return reached


def path_phrase(hop: dict[str, Any], nodes: dict[str, dict[str, Any]] | None = None) -> str:
    """Render a traversal path the way a digger would say it out loud, for the
    `why` field: 'Soundway → Analog Africa reissue → arranger Felipe Campuzano'."""
    nodes = load_nodes() if nodes is None else nodes
    names = [(nodes.get(n) or {}).get("name", n.split(":", 1)[-1]) for n in hop.get("path", [])]
    return " → ".join(names)


def stats() -> dict[str, Any]:
    nodes, edges = load_nodes(), load_edges()
    by_kind: dict[str, int] = {}
    for e in edges:
        by_kind[e.get("kind", "?")] = by_kind.get(e.get("kind", "?"), 0) + 1
    attested = sum(v for k, v in by_kind.items() if k in ATTESTED_EDGES)
    return {
        "nodes": len(nodes),
        "edges": len(edges),
        "edges_by_kind": by_kind,
        "attested_share": round(attested / len(edges), 3) if edges else 0.0,
    }
