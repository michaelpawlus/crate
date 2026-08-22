"""Recovering a stage response that was cut off mid-generation, and the
degradation contract that keeps a failed SEQUENCE from losing a whole dig."""

import json

import pytest

from crate import agent
from crate.pipeline import sequence

FULL = {
    "thesis": "A thesis sentence.",
    "order": [{"id": i, "rationale": f"rationale number {i}"} for i in range(15)],
}


def _truncate(fraction: float) -> str:
    text = json.dumps(FULL, indent=1)
    return text[: int(len(text) * fraction)]


# --- salvage ---

def test_complete_json_is_unaffected():
    assert agent.extract_json(json.dumps(FULL))["order"][-1]["id"] == 14


@pytest.mark.parametrize("fraction", [0.3, 0.5, 0.7, 0.9])
def test_truncated_response_keeps_the_entries_that_arrived(fraction):
    got = agent.extract_json(_truncate(fraction))
    assert got["thesis"] == "A thesis sentence."
    assert 0 < len(got["order"]) < 15
    # Every recovered entry must be whole, not a half-written one.
    assert all(set(e) == {"id", "rationale"} for e in got["order"])


def test_salvage_returns_none_for_unrecoverable_input():
    assert agent.salvage_truncated_json("not json at all") is None
    assert agent.salvage_truncated_json("") is None
    assert agent.salvage_truncated_json('{"a": ') is None


def test_salvage_does_not_break_on_brackets_inside_strings():
    text = '{"order": [{"id": 0, "rationale": "a } and a ] and a \\" quote"}, {"id": 1,'
    got = agent.salvage_truncated_json(text)
    assert len(got["order"]) == 1
    assert got["order"][0]["rationale"] == 'a } and a ] and a " quote'


def test_salvage_handles_a_truncated_top_level_array():
    text = json.dumps([{"id": i} for i in range(10)])
    got = agent.extract_json(text[: int(len(text) * 0.5)])
    assert 0 < len(got) < 10


def test_unparseable_response_writes_the_full_text_to_disk():
    """The exception truncates at 1000 chars, which cannot distinguish a cut-off
    response from a malformed one."""
    from crate import config

    junk = "prose only, no json here. " * 80
    with pytest.raises(agent.AgentError) as exc:
        agent.extract_json(junk)
    dumps = list((config.cache_dir() / "agent-failures").glob("*.txt"))
    assert len(dumps) == 1
    assert dumps[0].read_text() == junk
    assert str(dumps[0]) in str(exc.value)


# --- SEQUENCE degradation ---

def _selection(n=4):
    return [
        {"artist": f"A{i}", "track": f"T{i}", "score": 1.0 - i / 10, "conviction": "c"}
        for i in range(n)
    ]


def test_sequence_failure_falls_back_to_score_order(monkeypatch):
    """A reordering pass must never discard the pool, the traversal and the
    judging that produced it."""
    def _boom(*a, **kw):
        raise agent.AgentError("could not parse")

    monkeypatch.setattr(agent, "run_agent_json", _boom)
    out = sequence.run_sequence_stage(_selection(), {"brief": "", "sequencing": {}})
    assert [t["track"] for t in out["tracks"]] == ["T0", "T1", "T2", "T3"]
    assert [t["position"] for t in out["tracks"]] == [1, 2, 3, 4]
    assert out["sequencing_error"]


def test_sequence_failure_is_stated_not_hidden(monkeypatch):
    """A playlist presented in score order must not claim to be an argument."""
    monkeypatch.setattr(
        agent, "run_agent_json",
        lambda *a, **kw: (_ for _ in ()).throw(agent.AgentError("boom")),
    )
    out = sequence.run_sequence_stage(_selection(2), {"brief": "", "sequencing": {}})
    assert "failed" in out["thesis"]
    assert all("failed" in t["rationale"] for t in out["tracks"])


def test_a_partially_recovered_order_still_sequences(monkeypatch):
    """Salvage plus the existing append path: recovered entries lead, the rest
    follow in score order."""
    monkeypatch.setattr(
        agent, "run_agent_json",
        lambda *a, **kw: {"thesis": "T", "order": [{"id": 2, "rationale": "opener"}]},
    )
    out = sequence.run_sequence_stage(_selection(4), {"brief": "", "sequencing": {}})
    assert out["tracks"][0]["track"] == "T2"
    assert out["tracks"][0]["rationale"] == "opener"
    assert len(out["tracks"]) == 4
    assert "sequencing_error" not in out
