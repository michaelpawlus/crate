"""The three failures a real dig exposed: dead cross-source signal, compressed
ratings, and one source owning most of the playlist."""

from crate import config
from crate.pipeline import source, triangulate


def _c(artist, track, *sources, fit=0.8, stretch=0.5, also=None):
    """A candidate. `sources` mirrors what dedupe() attaches, since select()
    and score() read provenance from there, not from the raw `source` field."""
    d = {"artist": artist, "track": track, "fit": fit, "stretch": stretch,
         "source": sources[0] if sources else "", "why": "",
         "sources": [{"source": n, "why": ""} for n in sources]}
    if also:
        d["also_seen_in"] = also
    return d


# --- cross-source corroboration ---

def test_also_seen_in_creates_the_cross_source_signal():
    """The agent works one source at a time, so without a declared corroboration
    field the only overlap ever found is an accidental collision."""
    pool = triangulate.dedupe([_c("A", "T", "WFMU", also=[{"source": "NTS", "why": "played it"}])])
    assert [s["source"] for s in pool[0]["sources"]] == ["WFMU", "NTS"]
    assert pool[0]["sources"][1]["why"] == "played it"


def test_also_seen_in_accepts_bare_strings():
    pool = triangulate.dedupe([_c("A", "T", "WFMU", also=["NTS"])])
    assert [s["source"] for s in pool[0]["sources"]] == ["WFMU", "NTS"]


def test_also_seen_in_ignores_a_self_reference():
    pool = triangulate.dedupe([_c("A", "T", "WFMU", also=["WFMU"])])
    assert len(pool[0]["sources"]) == 1


def test_dedupe_merges_across_spelling_differences():
    """A tilde or a bracketed suffix must not cost the strongest quality signal
    the scorer has."""
    pool = triangulate.dedupe([
        _c("Los Camaroes", "Ma Wde Wde", "Analog Africa"),
        _c("Los Camarões", "Ma Wde Wdé (Remastered)", "Gilles Peterson"),
    ])
    assert len(pool) == 1
    assert len(pool[0]["sources"]) == 2


def test_dedupe_keeps_genuinely_different_tracks_apart():
    pool = triangulate.dedupe([
        _c("Ebo Taylor", "Heaven", "Strut"),
        _c("Ebo Taylor", "Love and Death", "Strut"),
        _c("Pat Thomas", "Heaven", "Strut"),
    ])
    assert len(pool) == 3


def test_match_key_is_looser_than_the_exclusion_key():
    """Exclusions must stay exact — a false merge there silently bans a track
    nobody banned."""
    from crate import state

    assert triangulate.match_key("Los Camarões", "Ma Wde Wdé") == triangulate.match_key(
        "Los Camaroes", "Ma Wde Wde"
    )
    assert state.track_key("Los Camarões", "Ma Wde Wdé") != state.track_key(
        "Los Camaroes", "Ma Wde Wde"
    )


# --- rating compression ---

def test_fit_ranks_spread_compressed_ratings():
    """The observed failure: four distinct values inside 0.75-0.85 reduce a 25%
    term to noise."""
    judged = [_c("A", str(i), fit=f) for i, f in enumerate([0.75, 0.78, 0.8, 0.85])]
    ranks = triangulate.fit_ranks(judged)
    assert min(ranks.values()) == 0.0
    assert max(ranks.values()) == 1.0
    # Order is preserved.
    assert ranks[0] < ranks[1] < ranks[2] < ranks[3]


def test_fit_ranks_give_ties_the_same_value():
    judged = [_c("A", str(i), fit=f) for i, f in enumerate([0.5, 0.9, 0.5, 0.9])]
    ranks = triangulate.fit_ranks(judged)
    assert ranks[0] == ranks[2]
    assert ranks[1] == ranks[3]
    assert ranks[0] < ranks[1]


def test_fit_ranks_handle_degenerate_and_tiny_pools():
    same = [_c("A", str(i), fit=0.8) for i in range(4)]
    assert len(set(triangulate.fit_ranks(same).values())) == 1
    assert triangulate.fit_ranks([_c("A", "T")]) == {0: 0.5}
    assert triangulate.fit_ranks([]) == {}


def test_rating_health_flags_the_observed_failure():
    judged = [_c("A", str(i), fit=f, stretch=0.5)
              for i, f in enumerate([0.75, 0.78, 0.8, 0.85] * 3)]
    health = triangulate.rating_health(judged)
    assert health["stretch_degenerate"] is True
    assert health["fit_degenerate"] is False  # four distinct values clears the floor
    assert health["fit_range"] == 0.1


def test_rating_health_is_quiet_on_a_well_spread_pool():
    judged = [_c("A", str(i), fit=i / 10, stretch=i / 10) for i in range(10)]
    health = triangulate.rating_health(judged)
    assert not health["fit_degenerate"]
    assert not health["stretch_degenerate"]


def test_ranked_fit_actually_widens_the_score_spread():
    """End to end: the compressed pool that produced a 0.038 spread."""
    judged = [_c("A", str(i), "WFMU", fit=f, stretch=0.5)
              for i, f in enumerate([0.75, 0.78, 0.80, 0.85, 0.85, 0.78])]
    spec = {"stretch_budget": 0.5, "length": 6}
    out = triangulate.select(judged, spec, {"WFMU": 0.8}, set())
    spread = max(t["score"] for t in out) - min(t["score"] for t in out)
    assert spread > 0.1


# --- source concentration ---

def test_no_single_source_owns_the_playlist():
    """The observed dig: Analog Africa supplied 5 of 15 and Habibi Funk 4, so
    two labels were most of the playlist. With the registry's minimum of four
    sources per run, the cap is always satisfiable."""
    from collections import Counter

    names = ["Analog Africa", "Habibi Funk", "WFMU", "NTS"]
    judged = [
        _c(f"A{i}", str(i), "Analog Africa", fit=0.95) for i in range(20)
    ]
    for offset, name in enumerate(names[1:], start=1):
        judged += [_c(f"B{offset}{i}", str(i), name, fit=0.5) for i in range(20)]
    spec = {"stretch_budget": 0.5, "length": 15}
    out = triangulate.select(judged, spec, {n: 0.8 for n in names}, set())

    assert len(out) == 15
    counts = Counter(t["sources"][0]["source"] for t in out)
    cap = max(1, int(15 * config.MAX_SOURCE_SHARE))
    assert counts["Analog Africa"] <= cap, counts
    # And it did not simply refuse the strongest source either.
    assert counts["Analog Africa"] == cap


def test_the_cap_is_satisfiable_at_the_registry_minimum():
    """MAX_SOURCE_SHARE and SOURCES_PER_RUN_MIN have to be compatible, or every
    dig quietly falls through to the yield path."""
    import math

    cap = max(1, math.floor(config.DEFAULT_LENGTH * config.MAX_SOURCE_SHARE))
    assert cap * config.SOURCES_PER_RUN_MIN >= config.DEFAULT_LENGTH


def test_the_cap_yields_rather_than_returning_a_short_playlist():
    """A lopsided playlist beats a truncated one."""
    judged = [_c("A", str(i), "Analog Africa") for i in range(15)]
    spec = {"stretch_budget": 0.5, "length": 15}
    out = triangulate.select(judged, spec, {"Analog Africa": 0.9}, set())
    assert len(out) == 15


def test_exploration_floor_survives_the_cap():
    """Two guardrails, and the floor is the one that exists to defeat tidying."""
    judged = [_c("A", str(i), "Big Source", fit=0.9) for i in range(20)]
    judged += [_c("C", str(i), "Cold Source", fit=0.1) for i in range(5)]
    spec = {"stretch_budget": 0.5, "length": 15}
    out = triangulate.select(
        judged, spec, {"Big Source": 0.9, "Cold Source": 0.5}, {"Cold Source"}
    )
    n_cold = sum(1 for t in out if t["sources"][0]["source"] == "Cold Source")
    assert n_cold >= 3  # ceil(15 * 0.20)


# --- source type spread ---

def _registry():
    out = []
    for i in range(6):
        out.append({"name": f"label{i}", "type": "reissue-label", "trust": 0.9, "feedback_count": 3})
    for i in range(2):
        out.append({"name": f"radio{i}", "type": "radio", "trust": 0.3, "feedback_count": 3})
        out.append({"name": f"pub{i}", "type": "publication", "trust": 0.3, "feedback_count": 3})
    return out


def test_rotation_spreads_across_source_types():
    """Five reissue labels is wide geographically and narrow structurally —
    every source in the set finds music the same way."""
    import random
    picked = source.pick_sources(_registry(), {"last_source_set": []}, random.Random(0))
    assert source.type_spread(picked) >= config.MIN_SOURCE_TYPES


def test_type_spread_degrades_on_a_single_type_registry():
    """A thin registry cannot do better and must not hang or return nothing."""
    import random
    only_labels = [
        {"name": f"l{i}", "type": "reissue-label", "trust": 0.8, "feedback_count": 0}
        for i in range(6)
    ]
    picked = source.pick_sources(only_labels, {"last_source_set": []}, random.Random(0))
    assert picked
    assert source.type_spread(picked) == 1
