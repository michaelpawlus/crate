"""`crate publish` — promoting a dry run to Spotify without re-digging."""

import pytest

from crate import config, state
from crate.pipeline import publish as publish_stage


def _dry_record(stamp="2026-07-30", n=3):
    return {
        "stamp": stamp,
        "brief": "",
        "thesis": "a thesis",
        "dry_run": True,
        "source_set": ["Soundway", "Light in the Attic"],
        "playlist_id": None,
        "playlist_url": None,
        "stretch_budget": 0.3,
        "tracks": [
            {
                "position": i,
                "artist": f"Artist {i}",
                "track": f"Track {i}",
                "album": f"Album {i}",
                "year": "1974",
                "conviction": "it slaps",
                "rationale": "the arc needs it",
                "sources": [{"source": "Soundway", "why": "on the comp"}],
                "stretch": 0.2,
                "score": 0.8,
            }
            for i in range(1, n + 1)
        ],
        "unresolved": [],
        "unresolved_count": 0,
    }


@pytest.fixture
def fake_spotify(monkeypatch):
    """Resolve everything, and record what got created."""
    calls = {}

    def search_track(track, artist, album=None):
        return {
            "uri": f"spotify:track:{track.replace(' ', '')}",
            "confidence": 0.95,
            "artists": artist,
            "name": track,
            "album": album or "",
        }

    def create_playlist(name, description, public=False):
        calls["created"] = {"name": name, "description": description, "public": public}
        return {"id": "pl123", "external_urls": {"spotify": "https://open.spotify.com/playlist/pl123"}}

    def add_tracks(playlist_id, uris):
        calls["added"] = {"playlist_id": playlist_id, "uris": uris}

    from crate import spotify

    monkeypatch.setattr(spotify, "search_track", search_track)
    monkeypatch.setattr(spotify, "create_playlist", create_playlist)
    monkeypatch.setattr(spotify, "add_tracks", add_tracks)
    return calls


def test_promote_publishes_without_redigging(fake_spotify):
    record = _dry_record()
    state.write_playlist_record(record["stamp"], record)

    out = publish_stage.promote_dry_run(record)

    assert out["dry_run"] is False
    assert out["playlist_url"].endswith("pl123")
    assert fake_spotify["created"]["public"] is False
    assert len(fake_spotify["added"]["uris"]) == 3
    # Persisted, not just returned.
    assert state.load_playlist_record("2026-07-30")["playlist_id"] == "pl123"


def test_promote_rewrites_liner_notes_with_the_published_record(fake_spotify):
    record = _dry_record()
    state.write_playlist_record(record["stamp"], record)
    out = publish_stage.promote_dry_run(record)
    notes = (config.history_dir() / "2026-07-30-liner-notes.md").read_text()
    assert "a thesis" in notes
    assert "Artist 1" in notes
    assert out["liner_notes_path"].endswith("2026-07-30-liner-notes.md")


def test_promote_does_not_double_count_signals(fake_spotify):
    """The dig already incremented playlists_generated, set last_source_set and
    appended used_tracks. Redoing that here would skew the drift-audit and
    meta-feedback cadences, which key off those counters."""
    record = _dry_record()
    state.write_playlist_record(record["stamp"], record)

    signals = state.load_signals()
    signals["playlists_generated"] = 4
    state.save_signals(signals)
    exclusions = state.load_exclusions()
    exclusions["used_tracks"] = [state.track_key("Artist 1", "Track 1")]
    state.save_exclusions(exclusions)

    publish_stage.promote_dry_run(record)

    assert state.load_signals()["playlists_generated"] == 4
    assert state.load_exclusions()["used_tracks"] == [state.track_key("Artist 1", "Track 1")]


def test_promote_reports_unresolved_and_still_publishes(fake_spotify, monkeypatch):
    from crate import spotify

    def picky(track, artist, album=None):
        if track == "Track 2":
            return None
        return {
            "uri": f"spotify:track:{track.replace(' ', '')}",
            "confidence": 0.95,
            "artists": artist,
            "name": track,
            "album": album or "",
        }

    monkeypatch.setattr(spotify, "search_track", picky)
    record = _dry_record()
    state.write_playlist_record(record["stamp"], record)

    out = publish_stage.promote_dry_run(record)

    assert out["unresolved_count"] == 1
    assert len(out["tracks"]) == 2
    # Positions are renumbered contiguously after the drop.
    assert [t["position"] for t in out["tracks"]] == [1, 2]
    assert (config.history_dir() / "2026-07-30-unresolved.md").exists()


def test_promote_raises_when_nothing_resolves(fake_spotify, monkeypatch):
    from crate import spotify

    monkeypatch.setattr(spotify, "search_track", lambda *a, **k: None)
    record = _dry_record()
    state.write_playlist_record(record["stamp"], record)

    with pytest.raises(RuntimeError, match="could be confidently matched"):
        publish_stage.promote_dry_run(record)
