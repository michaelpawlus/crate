from crate import spotify
from crate.pipeline.resolve import unresolved_report


def test_similarity_normalization():
    assert spotify._similarity("Love's Theme", "loves theme") > 0.8
    assert spotify._similarity("Song (Remastered 2019)", "Song  Remastered 2019") > 0.9


def test_pollution_terms_defined():
    assert "karaoke" in spotify.POLLUTION_TERMS
    assert "tribute" in spotify.POLLUTION_TERMS


def test_unresolved_report_contains_links_and_provenance():
    tracks = [
        {
            "track": "Deep Cut",
            "artist": "Obscure Artist",
            "album": "Lost LP",
            "year": "1974",
            "conviction": "the bassline",
            "sources": [{"source": "NTS", "why": "ep 12"}],
            "best_guess": {"confidence": 0.3, "artists": "Karaoke Band", "name": "Deep Cut"},
        }
    ]
    report = unresolved_report(tracks, "2026-07-08")
    assert "Obscure Artist" in report
    assert "bandcamp.com/search" in report
    assert "NTS" in report
    assert "rejected, confidence 0.3" in report
