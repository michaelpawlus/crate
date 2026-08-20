"""Graph store and traversal. No network: edges are constructed directly."""

from crate import graph


def _edge(src, dst, kind="played-on", **kw):
    return {"src": src, "dst": dst, "kind": kind, **kw}


def test_node_id_slugifies_and_namespaces():
    assert graph.node_id("artist", "Mulatu Astatke") == "artist:mulatu-astatke"
    assert graph.node_id("label", "Now-Again / Stones Throw") == "label:now-again-stones-throw"
    assert graph.node_id("artist", "  Mulatu Astatke  ") == "artist:mulatu-astatke"
    assert graph.node_id("artist", "") == ""


def test_node_id_folds_diacritics_to_one_identity():
    """Global music is full of them; without folding the graph holds two of
    everyone whose name is spelled both ways."""
    assert graph.node_id("artist", "Antonio Piñana Hijo") == graph.node_id(
        "artist", "Antonio Pinana Hijo"
    )
    assert graph.node_id("artist", "Antônio Carlos Jobim") == "artist:antonio-carlos-jobim"
    assert graph.node_id("artist", "Françoise Hardy") == "artist:francoise-hardy"


def test_node_id_falls_back_to_a_hash_when_a_name_folds_away():
    """An Amharic or Japanese name must get a node, not vanish. And `!!!` is a
    band, not an empty string."""
    amharic = graph.node_id("artist", "ሙላቱ አስታጥቄ")
    assert amharic.startswith("artist:x") and len(amharic) > len("artist:x")
    assert graph.node_id("artist", "ሙላቱ አስታጥቄ") == amharic  # stable
    assert graph.node_id("artist", "!!!") != graph.node_id("artist", "???")


def test_add_nodes_and_edges_are_idempotent():
    graph.add_nodes([{"kind": "artist", "name": "Alice Coltrane"}])
    graph.add_nodes([{"kind": "artist", "name": "Alice Coltrane"}])
    assert len(graph.load_nodes()) == 1

    e = _edge("artist:a", "release:b")
    assert graph.add_edges([e]) == 1
    assert graph.add_edges([e]) == 0
    assert len(graph.load_edges()) == 1


def test_edge_identity_is_src_dst_kind():
    """The same pair related two different ways is two edges; the same credit
    attested by two releases is one."""
    graph.add_edges([_edge("person:x", "release:y", "arranged", asserted_by="discogs:1")])
    graph.add_edges([_edge("person:x", "release:y", "arranged", asserted_by="discogs:2")])
    graph.add_edges([_edge("person:x", "release:y", "produced")])
    assert len(graph.load_edges()) == 2


def test_edges_carry_who_asserted_them():
    graph.add_edges([_edge("person:x", "release:y", "arranged", asserted_by="discogs:release/1")])
    edge = graph.load_edges()[0]
    assert edge["asserted_by"] == "discogs:release/1"
    assert 0.0 <= edge["confidence"] <= 1.0
    assert edge["added"]  # local civil date, like the rest of the codebase


def test_neighbors_are_undirected():
    graph.add_edges([_edge("person:x", "release:y")])
    assert len(graph.neighbors("person:x")) == 1
    assert len(graph.neighbors("release:y")) == 1
    assert graph.neighbors("release:zzz") == []


def test_walk_carries_the_path_that_reached_each_node():
    graph.add_nodes([
        {"kind": "artist", "name": "Seed"},
        {"kind": "release", "name": "Rec"},
        {"kind": "person", "name": "Arranger"},
    ])
    graph.add_edges([
        _edge("artist:seed", "release:rec"),
        _edge("person:arranger", "release:rec", "arranged", role="Arranged By"),
    ])
    hops = graph.walk(["artist:seed"], max_hops=2)
    by_id = {h["id"]: h for h in hops}
    assert by_id["release:rec"]["path"] == ["artist:seed", "release:rec"]
    assert by_id["person:arranger"]["path"] == ["artist:seed", "release:rec", "person:arranger"]
    assert graph.path_phrase(by_id["person:arranger"]) == "Seed → Rec → Arranger"


def test_walk_respects_hop_limit():
    graph.add_edges([_edge("a:1", "b:2"), _edge("b:2", "c:3")])
    assert [h["id"] for h in graph.walk(["a:1"], max_hops=1)] == ["b:2"]
    assert {h["id"] for h in graph.walk(["a:1"], max_hops=2)} == {"b:2", "c:3"}


def test_walk_terminates_on_a_cycle():
    graph.add_edges([_edge("a:1", "b:2"), _edge("b:2", "c:3"), _edge("c:3", "a:1")])
    hops = graph.walk(["a:1"], max_hops=5)
    assert len(hops) == len({h["id"] for h in hops})


def test_hand_edited_bad_line_is_skipped_not_fatal():
    """The file is meant to be hand-editable, so a broken line must cost one
    edge, not the graph."""
    graph.add_edges([_edge("a:1", "b:2")])
    with graph.edges_path().open("a") as f:
        f.write("{not json at all\n\n")
    graph.add_edges([_edge("c:3", "d:4")])
    assert len(graph.load_edges()) == 2


def test_stats_reports_attested_share():
    graph.add_edges([
        _edge("a:1", "b:2", "produced"),
        _edge("a:1", "c:3", "scene-member"),
    ])
    stats = graph.stats()
    assert stats["edges"] == 2
    assert stats["attested_share"] == 0.5
    assert graph.stats()["edges_by_kind"]["produced"] == 1
