"""INTENT: merge the per-run brief, taste.md, and taste-signals.json into a
run spec that downstream stages consume."""

import datetime
from typing import Any

from .. import config, state


def build_run_spec(brief: str | None, length: int | None) -> dict[str, Any]:
    signals = state.load_signals()
    taste = state.load_taste()
    weekday = datetime.date.today().strftime("%A")
    mood_prior = signals.get("mood_priors", {}).get(weekday, "")

    return {
        "stamp": state.today_stamp(),
        "weekday": weekday,
        "brief": brief or "",
        "mood_prior": mood_prior,
        "taste": taste,
        "length": length or config.DEFAULT_LENGTH,
        "familiarity_ratio": signals["familiarity_ratio"],
        # The learned budget, but exploration never drops below the floor.
        "stretch_budget": max(signals["stretch_budget"], config.EXPLORATION_FLOOR),
        "sequencing": signals.get("sequencing", {}),
        "signals": signals,
    }
