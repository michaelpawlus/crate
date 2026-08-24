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


def test_high_stretch_cut_falls_back_without_spread():
    """A single repeated stretch value is not evidence that everything is a
    reach — the cut must not collapse onto it."""
    flat = [{"stretch": 0.5, "value": 1.0} for _ in range(12)]
    assert learning.high_stretch_cut(flat) == config.HIGH_STRETCH_THRESHOLD
    assert learning.high_stretch_cut([]) == config.HIGH_STRETCH_THRESHOLD


def test_high_stretch_cut_never_exceeds_the_constant():
    """A dig that does use the full range keeps 0.6 as a reach; the observed
    cut may lower the bar, never raise it."""
    wide = [{"stretch": s, "value": 1.0} for s in (0.1, 0.2, 0.8, 0.9, 0.95, 0.99)]
    assert learning.high_stretch_cut(wide) <= config.HIGH_STRETCH_THRESHOLD


def test_budget_moves_on_a_compressed_stretch_distribution():
    """The regression that mattered: across the first two real digs the agent
    never proposed a stretch above 0.55, so an absolute 0.6 cut matched nothing
    and the budget was frozen. The observed distribution here is the real
    2026-08-22 one, whose top band was three loves out of three."""
    _seed_sources()
    session = [
        _fb("NTS", v, stretch=s, pos=i)
        for i, (s, v) in enumerate(
            [
                (0.35, "love"), (0.35, "fine"), (0.40, "love"),
                (0.45, "love"), (0.45, "love"), (0.45, "fine"),
                (0.50, "like"), (0.50, "like"), (0.50, "fine"),
                (0.55, "love"), (0.55, "love"), (0.55, "love"),
            ]
        )
    ]
    changes = learning.apply_feedback(session)
    assert changes["high_stretch_cut"] < config.HIGH_STRETCH_THRESHOLD
    assert changes["stretch_budget"]["new"] > changes["stretch_budget"]["old"]


def test_one_session_cannot_pin_a_source_to_the_ceiling():
    """Summed per-track deltas let four loves move a source +0.32 in a sitting,
    which parked the first session's two productive sources at the ceiling and
    made a 0.90-scoring source indistinguishable from a 0.74-scoring one."""
    state.save_sources(
        [
            {"name": "Numero Group", "type": "reissue-label", "trust": 0.95, "feedback_count": 0},
            {"name": "NTS", "type": "radio", "trust": 0.90, "feedback_count": 0},
        ]
    )
    session = [
        _fb("Numero Group", v, pos=i) for i, v in enumerate(["love"] * 4 + ["fine"])
    ] + [
        _fb("NTS", v, pos=10 + i) for i, v in enumerate(["love", "love", "like", "fine", "fine"])
    ]
    learning.apply_feedback(session)
    by = {s["name"]: s for s in state.load_sources()}
    assert by["Numero Group"]["trust"] < config.SOURCE_WEIGHT_CEIL
    assert by["NTS"]["trust"] < config.SOURCE_WEIGHT_CEIL
    # The better-performing source must still rank above the weaker one.
    assert by["Numero Group"]["trust"] > by["NTS"]["trust"]
    assert by["Numero Group"]["feedback_count"] == 5


def test_more_evidence_moves_trust_further_but_sublinearly():
    _seed_sources()
    learning.apply_feedback([_fb("NTS", "love", pos=i) for i in range(1)])
    one = {s["name"]: s for s in state.load_sources()}["NTS"]["trust"]
    _seed_sources()
    learning.apply_feedback([_fb("NTS", "love", pos=i) for i in range(8)])
    eight = {s["name"]: s for s in state.load_sources()}["NTS"]["trust"]
    assert eight > one
    assert (eight - 0.5) < 8 * (one - 0.5)
