"""All persistent state lives in human-readable files under ~/.crate.
The user may edit any of these by hand; manual edits are authoritative."""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

from . import config

DEFAULT_SIGNALS: dict[str, Any] = {
    # How far this listener can be stretched (0-1). Learned, but never below
    # the exploration floor.
    "stretch_budget": 0.5,
    # Share of anchor tracks (near taste centroid) vs. discoveries.
    "familiarity_ratio": 0.35,
    # Sequencing preferences: where the challenging track can land.
    "sequencing": {"left_turn_position": 4, "challenge_tolerance": 0.5},
    # Time-of-week mood priors, keyed by weekday name.
    "mood_priors": {},
    # Rotation state: source names used in the previous run.
    "last_source_set": [],
    "playlists_generated": 0,
    "feedback_sessions": 0,
    # Trailing record of (stretch_score, verdict) pairs for calibration.
    "stretch_history": [],
}


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


# --- sources.yaml ---

def load_sources() -> list[dict[str, Any]]:
    path = config.sources_path()
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text()) or {}
    return data.get("sources", [])


def save_sources(sources: list[dict[str, Any]]) -> None:
    path = config.sources_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"sources": sources}, sort_keys=False, allow_unicode=True))


def get_source(name: str) -> dict[str, Any] | None:
    for s in load_sources():
        if s["name"].lower() == name.lower():
            return s
    return None


# --- taste ---

def load_taste() -> str:
    path = config.taste_path()
    return path.read_text() if path.exists() else ""


def save_taste(text: str) -> None:
    config.taste_path().parent.mkdir(parents=True, exist_ok=True)
    config.taste_path().write_text(text)


def load_signals() -> dict[str, Any]:
    signals = dict(DEFAULT_SIGNALS)
    signals.update(_read_json(config.signals_path(), {}))
    return signals


def save_signals(signals: dict[str, Any]) -> None:
    _write_json(config.signals_path(), signals)


# --- exclusions ---

def load_exclusions() -> dict[str, Any]:
    return _read_json(
        config.exclusions_path(),
        {"artists": [], "tracks": [], "attributes": [], "used_tracks": []},
    )


def save_exclusions(exclusions: dict[str, Any]) -> None:
    _write_json(config.exclusions_path(), exclusions)


def track_key(artist: str, track: str) -> str:
    return f"{artist.strip().lower()} — {track.strip().lower()}"


def is_excluded(exclusions: dict[str, Any], artist: str, track: str) -> bool:
    key = track_key(artist, track)
    if key in exclusions.get("tracks", []) or key in exclusions.get("used_tracks", []):
        return True
    return artist.strip().lower() in [a.lower() for a in exclusions.get("artists", [])]


# --- history ---

def today_stamp() -> str:
    return date.today().isoformat()


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def playlist_record_path(stamp: str) -> Path:
    return config.history_dir() / f"{stamp}-playlist.json"


def write_history_file(stamp: str, suffix: str, content: str) -> Path:
    path = config.history_dir() / f"{stamp}-{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def write_playlist_record(stamp: str, record: dict[str, Any]) -> Path:
    path = playlist_record_path(stamp)
    _write_json(path, record)
    return path


def list_playlist_records() -> list[Path]:
    if not config.history_dir().exists():
        return []
    return sorted(config.history_dir().glob("*-playlist.json"))


def load_playlist_record(stamp_or_path: str | Path) -> dict[str, Any] | None:
    """Load one dig's record by stamp or path, or None if there is no such
    record. Returning None rather than raising is what lets the CLI's
    `if not record` guards emit the documented exit code 2; it also matches
    latest_playlist_record()'s contract."""
    path = Path(stamp_or_path)
    if not path.exists():
        path = playlist_record_path(str(stamp_or_path))
    if not path.exists():
        return None
    return json.loads(path.read_text())


def latest_playlist_record() -> dict[str, Any] | None:
    records = list_playlist_records()
    return json.loads(records[-1].read_text()) if records else None


def append_feedback(stamp: str, records: list[dict[str, Any]]) -> Path:
    path = config.history_dir() / f"{stamp}-feedback.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return path


def load_all_feedback() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not config.history_dir().exists():
        return out
    for path in sorted(config.history_dir().glob("*-feedback.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out
