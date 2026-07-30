from crate import seeds, state


def test_sources_roundtrip():
    state.save_sources(seeds.SEED_SOURCES)
    loaded = state.load_sources()
    assert len(loaded) == len(seeds.SEED_SOURCES)
    assert loaded[0]["name"] == seeds.SEED_SOURCES[0]["name"]


def test_signals_defaults_and_roundtrip():
    signals = state.load_signals()
    assert signals["stretch_budget"] == 0.5
    signals["stretch_budget"] = 0.7
    state.save_signals(signals)
    assert state.load_signals()["stretch_budget"] == 0.7


def test_exclusions():
    ex = state.load_exclusions()
    ex["artists"].append("Nickelback")
    ex["tracks"].append(state.track_key("Artist", "Song"))
    state.save_exclusions(ex)
    ex = state.load_exclusions()
    assert state.is_excluded(ex, "nickelback", "anything")
    assert state.is_excluded(ex, "Artist", "song")
    assert not state.is_excluded(ex, "Alice Coltrane", "Journey in Satchidananda")


def test_playlist_history_roundtrip():
    record = {"stamp": "2026-07-08", "thesis": "t", "tracks": []}
    state.write_playlist_record("2026-07-08", record)
    assert state.latest_playlist_record()["stamp"] == "2026-07-08"
    assert state.load_playlist_record("2026-07-08")["thesis"] == "t"


def test_missing_playlist_record_returns_none():
    """A stamp with no record must return None, not raise.

    The CLI's `if not record` guards in `history show` and `feedback` depend on
    this to emit the documented exit code 2; when this raised FileNotFoundError
    instead, both commands dumped a traceback and exited 1.
    """
    assert state.load_playlist_record("1999-01-01") is None
    assert state.latest_playlist_record() is None


def test_feedback_jsonl_roundtrip():
    recs = [{"playlist": "2026-07-08", "track_pos": 1, "verdict": "love"}]
    state.append_feedback("2026-07-08", recs)
    state.append_feedback("2026-07-08", recs)
    assert len(state.load_all_feedback()) == 2
