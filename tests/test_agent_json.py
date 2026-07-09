import pytest

from crate.agent import AgentError, extract_json, load_prompt


def test_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_fenced_json():
    text = 'Here you go:\n```json\n{"candidates": [1, 2]}\n```\nEnjoy.'
    assert extract_json(text) == {"candidates": [1, 2]}


def test_json_with_prose_around():
    text = 'Sure! [{"id": 0}] — that is all.'
    assert extract_json(text) == [{"id": 0}]


def test_unparseable_raises():
    with pytest.raises(AgentError):
        extract_json("no json here at all")


def test_prompts_load_and_substitute():
    for name in ("curator-system", "source", "triangulate", "sequence",
                 "feedback-parse", "taste-update", "interview"):
        text = load_prompt(name)
        assert len(text) > 100
    filled = load_prompt("triangulate", brief="test-brief-xyz", taste="t",
                         stretch_budget="0.5", candidates_json="[]")
    assert "test-brief-xyz" in filled
    assert "{{brief}}" not in filled
