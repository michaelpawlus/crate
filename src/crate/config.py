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
    for d in (crate_home(), history_dir(), cache_dir(), manual_dir()):
        d.mkdir(parents=True, exist_ok=True)
