from crate import config, learning, state


def _seed_sources():
    state.save_sources(
        [
            {"name": "NTS", "type": "radio", "trust": 0.5, "feedback_count": 0},
            {"name": "WFMU", "type": "radio", "trust": 0.5, "feedback_count": 0},
        ]
    )


def _fb(source, verdict, stretch=0.3, pos=1):
    return {
        "playlist": "2026-07-08",
        "track_pos": pos,
        "track": "a — b",
        "source": source,
        "verdict": verdict,
        "stretch_score": stretch,
    }


def test_loved_source_gains_weight():
    _seed_sources()
    learning.apply_feedback([_fb("NTS", "love"), _fb("NTS", "love", pos=2)])
    sources = {s["name"]: s for s in state.load_sources()}
    assert sources["NTS"]["trust"] > 0.5
    assert sources["NTS"]["feedback_count"] == 2


def test_weight_floor_holds():
    _seed_sources()
    hates = [_fb("WFMU", "hate", pos=i) for i in range(30)]
    learning.apply_feedback(hates)
    sources = {s["name"]: s for s in state.load_sources()}
    assert sources["WFMU"]["trust"] >= config.SOURCE_WEIGHT_FLOOR


def test_high_stretch_skip_discounted():
    _seed_sources()
    learning.apply_feedback([_fb("NTS", "skip", stretch=0.9)])
    high_stretch_trust = {s["name"]: s for s in state.load_sources()}["NTS"]["trust"]
    _seed_sources()
    learning.apply_feedback([_fb("NTS", "skip", stretch=0.1)])
    low_stretch_trust = {s["name"]: s for s in state.load_sources()}["NTS"]["trust"]
    assert high_stretch_trust > low_stretch_trust


def test_stretch_budget_moves_with_high_stretch_success():
    _seed_sources()
    loves = [_fb("NTS", "love", stretch=0.8, pos=i) for i in range(6)]
    changes = learning.apply_feedback(loves)
    assert changes["stretch_budget"]["new"] > changes["stretch_budget"]["old"]


def test_stretch_budget_never_below_exploration_floor():
    _seed_sources()
    signals = state.load_signals()
    signals["stretch_budget"] = config.EXPLORATION_FLOOR + 0.01
    state.save_signals(signals)
    for _ in range(5):
        skips = [_fb("NTS", "hate", stretch=0.8, pos=i) for i in range(6)]
        learning.apply_feedback(skips)
    assert state.load_signals()["stretch_budget"] >= config.EXPLORATION_FLOOR


def test_hate_adds_exclusion():
    _seed_sources()
    changes = learning.apply_feedback([_fb("NTS", "hate")])
    assert changes["exclusions_added"] == ["a — b"]
    assert "a — b" in state.load_exclusions()["tracks"]


def test_drift_check_needs_enough_history():
    assert learning.drift_check() is None


def test_diversity_index_contracts():
    diverse = [
        {
            "tracks": [
                {"artist": f"a{i}", "year": str(1960 + i * 5),
                 "sources": [{"source": f"s{i}"}]}
                for i in range(10)
            ]
        }
    ]
    narrow = [
        {
            "tracks": [
                {"artist": "same", "year": "2020", "sources": [{"source": "one"}]}
                for _ in range(10)
            ]
        }
    ]
    assert learning.diversity_index(diverse) > learning.diversity_index(narrow)
