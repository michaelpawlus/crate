"""Canon corpus. Pure file state, no network."""

from crate import canon


def test_starts_empty():
    assert canon.load() == []
    assert canon.digest() == ""


def test_add_anchor_creates_the_lineage_if_new():
    """Adding a record you love must not be blocked on naming a category."""
    canon.add_anchor("Ethio-jazz", "Mulatu Astatke", "Yekermo Sew", note="the template")
    lineage = canon.find("Ethio-jazz")
    assert lineage["anchors"] == [
        {"record": "Mulatu Astatke — Yekermo Sew", "note": "the template"}
    ]


def test_anchors_are_deduped_case_insensitively():
    canon.add_anchor("Ethio-jazz", "Mulatu Astatke", "Yekermo Sew")
    canon.add_anchor("ethio-JAZZ", "mulatu astatke", "yekermo sew")
    assert len(canon.load()) == 1
    assert len(canon.find("Ethio-jazz")["anchors"]) == 1


def test_add_lineage_updates_description_without_duplicating():
    canon.add_lineage("Ethio-jazz", "vibraphone over Amharic modes")
    canon.add_lineage("Ethio-jazz", "vibraphone over Amharic modes, 1969-1974")
    assert len(canon.load()) == 1
    assert "1969" in canon.find("Ethio-jazz")["what_it_does"]


def test_anchors_flattens_for_traversal_seeding():
    canon.add_anchor("Ethio-jazz", "Mulatu Astatke", "Yekermo Sew")
    canon.add_anchor("Spiritual jazz", "Alice Coltrane", "Journey in Satchidananda")
    seeds = canon.anchors()
    assert {s["artist"] for s in seeds} == {"Mulatu Astatke", "Alice Coltrane"}
    assert all(s["lineage"] for s in seeds)


def test_digest_renders_lineages_and_anchors():
    canon.add_anchor("Ethio-jazz", "Mulatu Astatke", "Yekermo Sew", note="the template")
    canon.add_lineage("Ethio-jazz", "vibraphone over Amharic modes")
    digest = canon.digest()
    assert "Ethio-jazz" in digest
    assert "vibraphone over Amharic modes" in digest
    assert "Mulatu Astatke — Yekermo Sew" in digest
    assert "the template" in digest


def test_touch_records_reference_for_the_decay_question(monkeypatch):
    canon.add_anchor("Ethio-jazz", "Mulatu Astatke", "Yekermo Sew")
    monkeypatch.setattr("crate.state.today_stamp", lambda: "2027-01-01")
    canon.touch(["ethio-jazz"])
    assert canon.find("Ethio-jazz")["last_referenced"] == "2027-01-01"


def test_touch_ignores_unknown_names():
    canon.add_anchor("Ethio-jazz", "Mulatu Astatke", "Yekermo Sew")
    canon.touch(["not a lineage"])
    canon.touch([])
    assert len(canon.load()) == 1


def test_manual_edits_survive_a_round_trip():
    """The file is authoritative — a hand-added key must not be dropped."""
    canon.add_anchor("Ethio-jazz", "Mulatu Astatke", "Yekermo Sew")
    lineages = canon.load()
    lineages[0]["retire_when"] = "no longer surprises me"
    canon.save(lineages)
    canon.add_anchor("Ethio-jazz", "Hailu Mergia", "Tezeta")
    assert canon.find("Ethio-jazz")["retire_when"] == "no longer surprises me"
