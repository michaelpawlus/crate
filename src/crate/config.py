"""Paths and hard constants. Guardrail constants here are deliberately not
stored in state files so the learning loop can never tune them."""

import os
from pathlib import Path


def crate_home() -> Path:
    return Path(os.environ.get("CRATE_HOME", str(Path.home() / ".crate")))


def sources_path() -> Path:
    return crate_home() / "sources.yaml"


def taste_path() -> Path:
    return crate_home() / "taste.md"


def signals_path() -> Path:
    return crate_home() / "taste-signals.json"


def exclusions_path() -> Path:
    return crate_home() / "exclusions.json"


def auth_path() -> Path:
    return crate_home() / "auth.json"


def history_dir() -> Path:
    return crate_home() / "history"


def cache_dir() -> Path:
    return crate_home() / "cache"


def graph_dir() -> Path:
    return crate_home() / "graph"


def canon_path() -> Path:
    return crate_home() / "canon.yaml"


def manual_dir() -> Path:
    return cache_dir() / "manual"


# --- Anti-convergence guardrails (§5.4). NOT tunable by the learning loop. ---

# Minimum share of every playlist drawn from sources/directions with no
# feedback history.
EXPLORATION_FLOOR = 0.20

# No source's trust weight may fall below this — even a cold source deserves
# occasional rotation.
SOURCE_WEIGHT_FLOOR = 0.10
SOURCE_WEIGHT_CEIL = 1.0

# A skip on a high-stretch track carries a fraction of the negative weight of
# a low-stretch skip (wrong-day/wrong-mood is not strong evidence).
HIGH_STRETCH_SKIP_DISCOUNT = 1 / 3
HIGH_STRETCH_THRESHOLD = 0.6

# Drift audit cadence and trigger.
DRIFT_AUDIT_EVERY = 8
DRIFT_CONTRACTION_LIMIT = 0.30

# Meta-feedback cadence ("are these getting more or less surprising?").
META_FEEDBACK_EVERY = 5

# --- Source incentive priors (P4). Multiplies how much a source's vouching
# counts, never the track itself. Gioia's master heuristic is "is this source
# paid to promote?", so the axis is structural self-interest, not quality:
# a label reissuing a record is promoting its own product even when its
# curation is excellent. Constants, like everything else in this block —
# the learning loop tunes trust, never the incentive prior. ---

INCENTIVE_PENALTY = {
    "none": 1.0,
    "low": 0.9,
    "medium": 0.75,
    "promotional": 0.5,
}
DEFAULT_INCENTIVE = "low"

# Fallback when a source predates the field and isn't in the seed table.
INCENTIVE_BY_TYPE = {
    "radio": "none",
    "individual": "none",
    "list-community": "none",
    "publication": "low",
    "reissue-label": "low",
}


def incentive_factor(source: dict) -> float:
    """Prior multiplier for one source's endorsement."""
    key = str(source.get("incentive") or DEFAULT_INCENTIVE)
    return INCENTIVE_PENALTY.get(key, INCENTIVE_PENALTY[DEFAULT_INCENTIVE])


# --- Credits graph (P9/P10/P13) ---

# How many records a single dig seeds the traversal from, and how far it walks.
GRAPH_SEEDS_PER_RUN = 6
GRAPH_MAX_HOPS = 2
# Hard ceiling on Discogs calls per dig. Unauthenticated Discogs allows 25
# req/min; cached_fetch absorbs repeats, but a cold dig must still not stall.
GRAPH_REQUEST_BUDGET = 40
# Credit roles worth traversing. Everything else on a release (photography,
# liner notes, mastering) is real provenance but a poor predictor of sound.
GRAPH_CREATIVE_ROLES = (
    "producer",
    "arranged by",
    "arranger",
    "written-by",
    "composed by",
    "directed by",
    "conductor",
    "bass",
    "drums",
    "guitar",
    "keyboards",
    "piano",
    "organ",
    "saxophone",
    "trumpet",
    "percussion",
    "vocals",
    "engineer",
    "mixed by",
)

# --- Run defaults ---

DEFAULT_LENGTH = 15
CANDIDATE_POOL_MIN = 60
CANDIDATE_POOL_MAX = 120
SOURCES_PER_RUN_MIN = 4
SOURCES_PER_RUN_MAX = 7

# RESOLVE: below this match confidence, drop the track rather than risk a
# wrong version (cover/karaoke pollution).
RESOLVE_CONFIDENCE_THRESHOLD = 0.62

SPOTIFY_REDIRECT_PORT = 8765
SPOTIFY_REDIRECT_URI = f"http://127.0.0.1:{SPOTIFY_REDIRECT_PORT}/callback"
SPOTIFY_SCOPES = "playlist-modify-private playlist-modify-public user-top-read"

CACHE_TTL_SECONDS = 24 * 3600


def ensure_dirs() -> None:
    for d in (crate_home(), history_dir(), cache_dir(), manual_dir(), graph_dir()):
        d.mkdir(parents=True, exist_ok=True)
