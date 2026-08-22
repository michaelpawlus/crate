"""Credits traversal. Discogs is stubbed — tests never touch the network."""

import pytest

from crate import canon, config, discogs, graph, lineage, state

RELEASE = {
    "id": 1479758,
    "title": "Sevillanas '72 Vol. 2",
    "year": 1972,
    "labels": [{"name": "Hispavox"}],
    "extraartists": [
        {"id": 11, "name": "Felipe Campuzano", "role": "Arranged By [Arreglos], Directed By"},
        {"id": 12, "name": "Antonio Piñana Hijo", "role": "Guitar"},
        {"id": 13, "name": "Villena", "role": "Photography"},
        {"id": 14, "name": "Aurelio Verde", "role": "Written-by [Autores]"},
    ],
}


@pytest.fixture
def stub_discogs(monkeypatch):
    """One release, always found. Counts calls so budget behaviour is visible."""
    calls = {"search": 0, "release": 0}

    def _search(artist, title="", budget=None):
        calls["search"] += 1
        if budget is not None and not budget.take():
            return None
        return {"id": RELEASE["id"], "title": RELEASE["title"]}

    def _release(release_id, budget=None):
        calls["release"] += 1
        if budget is not None and not budget.take():
            return None
        return RELEASE

    monkeypatch.setattr(discogs, "search_release", _search)
    monkeypatch.setattr(discogs, "release", _release)
    return calls


# --- credit filtering (pure, no stub needed) ---

def test_credits_keep_creative_roles_and_drop_the_rest():
    names = {c["name"] for c in discogs.credits(RELEASE)}
    assert "Felipe Campuzano" in names
    assert "Antonio Piñana Hijo" in names
    assert "Villena" not in names  # photography is provenance, not sound


def test_credits_match_roles_inside_bracketed_free_text():
    """Discogs roles are free text — `Arranged By [Arreglos], Directed By` has
    to match on substring or the richest credits are silently dropped."""
    got = [c for c in discogs.credits(RELEASE) if c["name"] == "Felipe Campuzano"]
    assert len(got) == 1


def test_credits_tolerate_missing_payload():
    assert discogs.credits(None) == []
    assert discogs.credits({}) == []
    assert discogs.labels(None) == []


def test_credits_dedupe_the_same_person_in_the_same_role():
    doubled = {**RELEASE, "extraartists": RELEASE["extraartists"] + [
        {"id": 12, "name": "Antonio Piñana Hijo", "role": "Guitar"}
    ]}
    assert len(discogs.credits(doubled)) == len(discogs.credits(RELEASE))


# --- budget ---

def test_budget_stops_spending_at_the_limit():
    budget = discogs.Budget(limit=2)
    assert budget.take() and budget.take()
    assert not budget.take()
    assert budget.spent == 2


def test_build_stops_once_the_budget_is_exhausted(stub_discogs):
    records = [{"artist": f"A{i}", "track": "t", "origin": "x"} for i in range(10)]
    summary = lineage.build_from_records(records, budget=discogs.Budget(limit=4))
    assert summary["requests_spent"] == 4
    assert summary["records_resolved"] < len(records)


# --- graph construction ---

def test_build_records_attested_edges(stub_discogs):
    summary = lineage.build_from_records(
        [{"artist": "Felipe Campuzano", "track": "Sevillanas", "origin": "WFMU"}]
    )
    assert summary["records_resolved"] == 1
    edges = graph.load_edges()
    kinds = {e["kind"] for e in edges}
    assert "released-on" in kinds
    assert "arranged" in kinds
    assert all(e["asserted_by"].startswith("discogs:release/") for e in edges)


def test_role_maps_to_edge_kind():
    assert lineage._edge_kind_for("Producer") == "produced"
    assert lineage._edge_kind_for("Arranged By [Arreglos]") == "arranged"
    assert lineage._edge_kind_for("Directed By") == "arranged"
    assert lineage._edge_kind_for("Written-by [Autores]") == "written-by"
    assert lineage._edge_kind_for("Guitar") == "played-on"


def test_build_is_idempotent_across_runs(stub_discogs):
    rec = [{"artist": "Felipe Campuzano", "track": "Sevillanas", "origin": "WFMU"}]
    lineage.build_from_records(rec)
    before = len(graph.load_edges())
    second = lineage.build_from_records(rec)
    assert second["edges_added"] == 0
    assert len(graph.load_edges()) == before


# --- seeding ---

def test_canon_anchors_seed_the_traversal_first():
    """Canon leads because it is the stable part of the listener's world."""
    canon.add_anchor("Ethio-jazz", "Mulatu Astatke", "Yekermo Sew")
    material = {"WFMU": {"material": [{"artist": "Someone Else", "title": "x"}]}}
    seeds = lineage.seed_records(material, limit=5)
    assert seeds[0]["artist"] == "Mulatu Astatke"
    assert seeds[0]["origin"] == "canon:Ethio-jazz"


def test_canon_cannot_take_every_seed_slot():
    """A big canon must not starve tonight's material — the live half of the
    seed mix is the half that makes the graph grow."""
    for i in range(20):
        canon.add_anchor("Big", f"Artist {i}", "t")
    material = {"WFMU": {"material": [{"artist": "Tonight", "title": "x"}]}}
    seeds = lineage.seed_records(material, limit=6)
    origins = [s["origin"] for s in seeds]
    assert sum(o.startswith("canon:") for o in origins) <= 3
    assert "WFMU" in origins


def test_canon_seeds_rotate_across_digs():
    """A large canon should be traversed over several nights, not just its head."""
    for i in range(20):
        canon.add_anchor("Big", f"Artist {i}", "t")

    def canon_seeds():
        return {
            s["artist"] for s in lineage.seed_records({}, limit=6)
            if s["origin"].startswith("canon:")
        }

    first = canon_seeds()
    signals = state.load_signals()
    signals["playlists_generated"] = 1
    state.save_signals(signals)
    assert canon_seeds() != first


def test_canon_seeding_is_deterministic_within_one_dig():
    for i in range(20):
        canon.add_anchor("Big", f"Artist {i}", "t")
    assert lineage.seed_records({}, limit=6) == lineage.seed_records({}, limit=6)


def test_a_single_anchor_still_seeds():
    """The share is a ceiling, not a quota — one anchor must not round to zero."""
    canon.add_anchor("Ethio-jazz", "Mulatu Astatke", "Yekermo Sew")
    seeds = lineage.seed_records({}, limit=2)
    assert seeds[0]["artist"] == "Mulatu Astatke"


def test_seed_records_finds_tracks_in_nested_fetcher_shapes():
    """Each fetcher returns a different shape; the walker must not assume one."""
    material = {
        "NTS": {"material": {"floating-points": [
            {"episode": "e", "tracklist": [{"artist": "Hailu Mergia", "title": "Tezeta"}]}
        ]}},
        "BBC 6 Music": {"material": [{"artist": "Sault", "title": "Wildfires"}]},
    }
    artists = {s["artist"] for s in lineage.seed_records(material, limit=10)}
    assert artists == {"Hailu Mergia", "Sault"}


def test_seed_records_dedupes_and_respects_the_limit():
    material = {
        "A": {"material": [{"artist": "X", "title": "t"}]},
        "B": {"material": [{"artist": "X", "title": "T"}]},
        "C": {"material": [{"artist": f"Y{i}", "title": "t"} for i in range(10)]},
    }
    seeds = lineage.seed_records(material, limit=4)
    assert len(seeds) == 4
    assert len([s for s in seeds if s["artist"] == "X"]) == 1


def test_loved_tracks_seed_the_traversal():
    state.append_feedback("2026-08-20", [
        {"track": "Hailu Mergia — Tezeta", "verdict": "love", "track_pos": 1},
        {"track": "Someone — Meh", "verdict": "skip", "track_pos": 2},
    ])
    seeds = lineage.seed_records({}, limit=10)
    assert [s["artist"] for s in seeds] == ["Hailu Mergia"]


def test_seed_records_survives_empty_material():
    assert lineage.seed_records({}, limit=5) == []
    assert lineage.seed_records({"A": {"material": None}}, limit=5) == []


# --- neighborhood ---

def test_neighborhood_returns_people_and_labels_with_their_paths(stub_discogs):
    records = [{"artist": "Felipe Campuzano", "track": "Sevillanas", "origin": "WFMU"}]
    lineage.build_from_records(records)
    leads = lineage.neighborhood(records)
    kinds = {lead["kind"] for lead in leads}
    assert kinds <= {"artist", "label"}
    assert any(lead["name"] == "Hispavox" for lead in leads)
    assert all(lead["attested_by"].startswith("discogs:") for lead in leads)
    assert all("→" in lead["path"] for lead in leads)


def test_neighborhood_never_leads_back_to_a_seed(stub_discogs):
    """Felipe Campuzano is both the seed artist and a credit on his own record.
    A lead back to where you started is not a lead."""
    records = [{"artist": "Felipe Campuzano", "track": "Sevillanas", "origin": "WFMU"}]
    lineage.build_from_records(records)
    leads = lineage.neighborhood(records)
    assert leads, "expected the other credits to survive"
    assert not any(lead["name"] == "Felipe Campuzano" for lead in leads)


def test_neighborhood_dedupes_leads_by_name(stub_discogs):
    records = [{"artist": "Someone", "track": "x", "origin": "WFMU"}]
    lineage.build_from_records(records)
    leads = lineage.neighborhood(records)
    assert len(leads) == len({lead["name"] for lead in leads})


def test_a_credited_person_and_a_performing_artist_are_one_node(stub_discogs):
    """The drummer on one record is the bandleader on another — splitting the
    namespaces would hide exactly the connection worth traversing."""
    lineage.build_from_records(
        [{"artist": "Antonio Piñana Hijo", "track": "x", "origin": "WFMU"}]
    )
    ids = set(graph.load_nodes())
    assert "artist:antonio-pinana-hijo" in ids  # diacritics folded
    assert not any(i.startswith("person:") for i in ids)


def test_neighborhood_is_empty_when_the_graph_has_nothing():
    assert lineage.neighborhood([{"artist": "Nobody", "track": "t"}]) == []


def test_graph_max_hops_is_a_constant_not_state():
    """The traversal depth is a guardrail — the learning loop must not tune it."""
    assert isinstance(config.GRAPH_MAX_HOPS, int)
    assert "GRAPH_MAX_HOPS" not in state.DEFAULT_SIGNALS


# --- match confidence: drop, never substitute ---

def test_artist_match_accepts_the_real_thing():
    assert discogs.artist_matches("ear", "Ear (11) - Rumspringa")
    assert discogs.artist_matches("Alice Coltrane", "Alice Coltrane - Journey In Satchidananda")
    assert discogs.artist_matches("Mulatu Astatke", "Mulatu Astatke - Mulatu Plays Mulatu")
    # Diacritics and punctuation differences are not a mismatch.
    assert discogs.artist_matches("Antonio Pinana Hijo", "Antonio Piñana Hijo - Some Record")


def test_artist_match_accepts_an_artist_billed_with_their_band():
    """The norm in this corpus. A strict whole-string ratio rejects all of
    these, which silently shrinks the graph to anglophone solo credits."""
    assert discogs.artist_matches("Hailu Mergia", "Hailu Mergia & The Walias Band* - Tezeta")
    assert discogs.artist_matches("Mulatu Astatke", "Mulatu Astatke & His Ethiopian Quintet - Afro-Latin Soul")
    assert discogs.artist_matches("K. Frimpong", "K. Frimpong & His Cubano Fiestas - Hwehwe Mu Na Yi Wo Mpena")
    # And the reverse billing, where the query is the longer name.
    assert discogs.artist_matches("Ebo Taylor & The Pelikans", "Ebo Taylor - Life Stories")


def test_artist_match_still_refuses_a_shared_prefix_that_is_a_different_artist():
    """Leading-token containment, not substring — otherwise "ear" swallows
    "Earth, Wind & Fire"."""
    assert not discogs.artist_matches("ear", "Earth, Wind & Fire - That's the Way of the World")
    assert not discogs.artist_matches("Sun Ra", "Sunny Day Real Estate - Diary")


def test_artist_match_rejects_a_fuzzy_hit_on_a_different_artist():
    """The live failure this was written for: searching ("ear", "Coil") returns
    Maveth's "Coils Of The Black Earth" with no sign it is unrelated."""
    assert not discogs.artist_matches("ear", "Maveth - Coils Of The Black Earth")
    assert not discogs.artist_matches("Big Thief", "Coil - Windowpane")
    assert not discogs.artist_matches("Sault", "Sonic Youth - Daydream Nation")


def test_artist_match_rejects_empty_input():
    assert not discogs.artist_matches("", "Coil - Windowpane")
    assert not discogs.artist_matches("ear", "")


def test_search_release_drops_rather_than_substituting(monkeypatch):
    monkeypatch.setattr(
        discogs, "_get",
        lambda *a, **kw: {"results": [{"id": 1, "title": "Maveth - Coils Of The Black Earth"}]},
    )
    assert discogs.search_release("ear", "Coil") is None


def test_search_release_skips_past_a_bad_first_result(monkeypatch):
    """Discogs orders by its own relevance, which is not ours."""
    monkeypatch.setattr(
        discogs, "_get",
        lambda *a, **kw: {"results": [
            {"id": 1, "title": "Maveth - Coils Of The Black Earth"},
            {"id": 2, "title": "Ear (11) - Rumspringa"},
        ]},
    )
    assert discogs.search_release("ear", "Coil")["id"] == 2


def test_a_dropped_match_costs_a_seed_not_the_traversal(monkeypatch):
    monkeypatch.setattr(discogs, "search_release", lambda *a, **kw: None)
    summary = lineage.build_from_records([{"artist": "ear", "track": "Coil", "origin": "canon"}])
    assert summary["records_resolved"] == 0
    assert summary["edges_added"] == 0
