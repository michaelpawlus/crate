import math

from crate import config
from crate.pipeline import triangulate


def _cand(track, artist, source, **kw):
    c = {"track": track, "artist": artist, "source": source, "why": "w"}
    c.update(kw)
    return c


def test_dedupe_merges_cross_source():
    pool = triangulate.dedupe(
        [
            _cand("Song A", "Artist X", "NTS"),
            _cand("song a", "artist x", "WFMU"),
            _cand("Song B", "Artist Y", "NTS"),
        ]
    )
    assert len(pool) == 2
    merged = next(c for c in pool if c["track"] == "Song A")
    assert {s["source"] for s in merged["sources"]} == {"NTS", "WFMU"}


def test_cross_source_beats_single_source():
    trust = {"NTS": 0.8, "WFMU": 0.8}
    single = {"track": "a", "artist": "x", "sources": [{"source": "NTS"}], "fit": 0.5, "stretch": 0.5}
    double = {"track": "b", "artist": "y", "sources": [{"source": "NTS"}, {"source": "WFMU"}], "fit": 0.5, "stretch": 0.5}
    budget = 0.5
    assert triangulate.score(double, trust, budget, set()) > triangulate.score(
        single, trust, budget, set()
    )


def test_stretch_rewarded_up_to_budget_then_penalized():
    assert triangulate.stretch_reward(0.5, 0.5) == 1.0
    assert triangulate.stretch_reward(0.2, 0.5) < 1.0
    assert triangulate.stretch_reward(0.9, 0.5) < triangulate.stretch_reward(0.5, 0.5)


def test_top_track_overlap_penalized():
    trust = {"NTS": 0.8}
    c = {"track": "Hit", "artist": "Big", "sources": [{"source": "NTS"}], "fit": 0.9, "stretch": 0.3}
    from crate import state

    with_penalty = triangulate.score(c, trust, 0.5, {state.track_key("Big", "Hit")})
    without = triangulate.score(c, trust, 0.5, set())
    assert without - with_penalty >= 0.2


def test_selection_enforces_exploration_floor():
    trust = {"Hot": 1.0, "Cold": 0.3}
    judged = []
    for i in range(20):
        judged.append(
            {"track": f"h{i}", "artist": f"a{i}", "sources": [{"source": "Hot"}],
             "fit": 0.9, "stretch": 0.4, "conviction": "x"}
        )
    for i in range(5):
        judged.append(
            {"track": f"c{i}", "artist": f"b{i}", "sources": [{"source": "Cold"}],
             "fit": 0.2, "stretch": 0.4, "conviction": "x"}
        )
    run_spec = {"length": 10, "stretch_budget": 0.5}
    selection = triangulate.select(judged, run_spec, trust, cold_sources={"Cold"})
    n_cold = sum(
        1 for c in selection if any(s["source"] == "Cold" for s in c["sources"])
    )
    assert len(selection) == 10
    assert n_cold >= math.ceil(10 * config.EXPLORATION_FLOOR)
