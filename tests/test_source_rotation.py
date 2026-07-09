import random

from crate import config
from crate.pipeline.source import pick_sources


def _registry(n=10, cold_from=7):
    return [
        {"name": f"s{i}", "trust": 0.8, "feedback_count": 0 if i >= cold_from else 5}
        for i in range(n)
    ]


def test_never_same_set_twice():
    sources = _registry()
    rng = random.Random(42)
    signals = {"last_source_set": []}
    first = {s["name"] for s in pick_sources(sources, signals, rng)}
    signals["last_source_set"] = list(first)
    second = {s["name"] for s in pick_sources(sources, signals, rng)}
    assert first != second


def test_exploration_sources_included():
    sources = _registry()
    rng = random.Random(7)
    for _ in range(10):
        picked = pick_sources(sources, {"last_source_set": []}, rng)
        cold = [s for s in picked if s["feedback_count"] == 0]
        assert len(cold) >= 1


def test_pick_count_in_range():
    sources = _registry(20)
    rng = random.Random(1)
    picked = pick_sources(sources, {"last_source_set": []}, rng)
    assert config.SOURCES_PER_RUN_MIN <= len(picked) <= config.SOURCES_PER_RUN_MAX
