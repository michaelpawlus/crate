"""The incentive prior (P4) and how it discounts vouching in TRIANGULATE."""

import pytest

from crate import config, seeds, state
from crate.pipeline import triangulate


def _candidate(*source_names, fit=0.5, stretch=0.5):
    return {
        "artist": "A", "track": "T", "fit": fit, "stretch": stretch,
        "sources": [{"source": n, "why": ""} for n in source_names],
    }


def test_every_seed_source_declares_an_incentive():
    for src in seeds.SEED_SOURCES:
        assert src.get("incentive") in config.INCENTIVE_PENALTY, src["name"]


def test_incentive_factor_falls_back_for_an_unknown_value():
    assert config.incentive_factor({"incentive": "none"}) == 1.0
    assert config.incentive_factor({"incentive": "nonsense"}) == (
        config.INCENTIVE_PENALTY[config.DEFAULT_INCENTIVE]
    )
    assert config.incentive_factor({}) == config.INCENTIVE_PENALTY[config.DEFAULT_INCENTIVE]


def test_promotional_source_scores_below_a_disinterested_one():
    trust = {"Indie DJ": 0.8, "Label PR": 0.8}
    incentive = {"Indie DJ": 1.0, "Label PR": 0.5}
    clean = triangulate.score(_candidate("Indie DJ"), trust, 0.5, set(), incentive)
    promo = triangulate.score(_candidate("Label PR"), trust, 0.5, set(), incentive)
    assert clean > promo


def test_incentive_discounts_vouching_not_the_music():
    """Fit and stretch come from judging the record; only provenance and
    corroboration are discounted."""
    trust = {"Label PR": 0.8}
    incentive = {"Label PR": 0.5}
    low_fit = triangulate.score(_candidate("Label PR", fit=0.2), trust, 0.5, set(), incentive)
    high_fit = triangulate.score(_candidate("Label PR", fit=0.9), trust, 0.5, set(), incentive)
    # The fit term is worth 0.25 of the total and must arrive undiscounted.
    assert high_fit - low_fit == pytest.approx(0.25 * 0.7, abs=1e-3)


def test_two_promotional_sources_corroborate_more_weakly_than_two_clean_ones():
    trust = {"A": 0.8, "B": 0.8, "P": 0.8, "Q": 0.8}
    incentive = {"A": 1.0, "B": 1.0, "P": 0.5, "Q": 0.5}
    clean = triangulate.score(_candidate("A", "B"), trust, 0.5, set(), incentive)
    promo = triangulate.score(_candidate("P", "Q"), trust, 0.5, set(), incentive)
    assert clean > promo


def test_missing_incentive_map_leaves_scoring_unchanged():
    """Callers that don't pass the map (older tests, ad-hoc use) get the
    previous behaviour rather than a silent penalty."""
    trust = {"A": 0.8}
    assert triangulate.score(_candidate("A"), trust, 0.5, set()) == triangulate.score(
        _candidate("A"), trust, 0.5, set(), {"A": 1.0}
    )


def test_backfill_uses_the_seed_judgement_over_the_type_fallback():
    """BBC 6 Music is `medium` because its rotation is playlisted, while the
    per-type fallback for radio is `none`. The named judgement must win."""
    sources, filled = state.backfill_source_defaults(
        [{"name": "BBC 6 Music", "type": "radio"}]
    )
    assert sources[0]["incentive"] == "medium"
    assert filled == ["BBC 6 Music"]


def test_backfill_falls_back_by_type_for_an_unknown_source():
    sources, filled = state.backfill_source_defaults(
        [{"name": "Some New Blog", "type": "publication"}]
    )
    assert sources[0]["incentive"] == config.INCENTIVE_BY_TYPE["publication"]
    assert filled == ["Some New Blog"]


def test_backfill_never_overwrites_a_hand_set_value():
    sources, filled = state.backfill_source_defaults(
        [{"name": "BBC 6 Music", "type": "radio", "incentive": "none"}]
    )
    assert sources[0]["incentive"] == "none"
    assert filled == []


def test_backfill_handles_a_source_with_no_type():
    sources, _ = state.backfill_source_defaults([{"name": "Mystery"}])
    assert sources[0]["incentive"] == config.DEFAULT_INCENTIVE
