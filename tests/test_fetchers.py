"""Fetcher regressions for the three sources that went dead by 2026-07-30.

Every test here is hermetic — the network paths are monkeypatched. The live
verification that produced these fixes is recorded in docs/source-access.md.
"""

import httpx
import pytest

from crate import fetchers


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.test")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


# --- reddit: the JSON API is gone; the Atom feed is not ---

@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        # What every registry seeded before 2026-07-30 has on file.
        (
            "https://www.reddit.com/r/listentothis/top.json?t=month",
            "https://www.reddit.com/r/listentothis/top.rss?t=month",
        ),
        # Already migrated — must be left alone, not double-suffixed.
        (
            "https://www.reddit.com/r/listentothis/top.rss?t=month",
            "https://www.reddit.com/r/listentothis/top.rss?t=month",
        ),
        # No suffix at all.
        (
            "https://www.reddit.com/r/listentothis/top",
            "https://www.reddit.com/r/listentothis/top.rss",
        ),
    ],
)
def test_reddit_url_normalised_to_atom(stored, expected):
    assert fetchers._reddit_feed_url(stored) == expected


def test_reddit_parses_atom_titles(monkeypatch):
    atom = b"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Yomi Ship - Devil Djinn [math rock] (2026)</title>
             <link href="https://reddit.com/a"/></entry>
      <entry><title>Tuffie - Eraser [indie rock] (2026)</title>
             <link href="https://reddit.com/b"/></entry>
    </feed>"""
    monkeypatch.setattr(fetchers, "_get_bytes", lambda url, **kw: atom)
    out = fetchers.fetch_reddit_top("https://www.reddit.com/r/listentothis/top.json?t=month")
    assert [o["title"] for o in out] == [
        "Yomi Ship - Devil Djinn [math rock] (2026)",
        "Tuffie - Eraser [indie rock] (2026)",
    ]


def test_reddit_429_degrades_to_empty_not_error(monkeypatch):
    """Reddit rate-limits the feed readily. This source is corroboration-only,
    so a 429 must not mark it dead in `crate doctor`."""

    def boom(url, **kw):
        raise _http_error(429)

    monkeypatch.setattr(fetchers, "_get_bytes", boom)
    assert fetchers.fetch_reddit_top("https://www.reddit.com/r/listentothis/top.rss") == []


def test_reddit_other_errors_still_raise(monkeypatch):
    def boom(url, **kw):
        raise _http_error(500)

    monkeypatch.setattr(fetchers, "_get_bytes", boom)
    with pytest.raises(httpx.HTTPStatusError):
        fetchers.fetch_reddit_top("https://www.reddit.com/r/listentothis/top.rss")


# --- NTS: the route is fine, the show aliases rot ---

def test_nts_dead_alias_returns_error_marker_not_raise(monkeypatch):
    def boom(url, **kw):
        raise _http_error(404)

    monkeypatch.setattr(fetchers, "_get_json", boom)
    result = fetchers.fetch_nts_show("zakia")
    assert "error" in result
    assert "zakia" in result["error"]


def test_nts_one_dead_alias_does_not_sink_the_source(monkeypatch):
    """The regression that took NTS out entirely: fetch_nts_show ran inside a
    dict comprehension, so the first 404 propagated and the whole source was
    reported dead — including shows that were fetching fine."""
    calls = {}

    def fake(alias, episodes=3):
        calls[alias] = True
        if alias == "dead-show":
            return {"error": f"show alias '{alias}' not found (404)"}
        return [{"episode": f"{alias} ep", "date": "2026-07-27", "tracklist": []}]

    monkeypatch.setattr(fetchers, "fetch_nts_show", fake)
    out = fetchers.gather_source_material(
        {"name": "NTS", "access": "api", "shows": ["dead-show", "floating-points"]}
    )
    assert "floating-points" in out["material"]
    assert "dead-show" not in out["material"]
    assert "dead show alias" in out["fetch_status"]
    assert "dead-show" in out["fetch_status"]


def test_nts_all_aliases_dead_reports_error(monkeypatch):
    monkeypatch.setattr(
        fetchers, "fetch_nts_show", lambda alias, episodes=3: {"error": "gone"}
    )
    out = fetchers.gather_source_material(
        {"name": "NTS", "access": "api", "shows": ["a", "b"]}
    )
    assert out["material"] is None
    assert out["fetch_status"].startswith("error: all show aliases dead")


# --- BBC: the page-limit ceiling tightened to 10 ---

def test_bbc_limit_clamped_to_api_maximum(monkeypatch):
    """limit=30 returned 400 'Page limit must be between 1 and 10'."""
    seen = {}

    def fake_get_json(url, **kw):
        seen["url"] = url
        return {"data": []}

    monkeypatch.setattr(fetchers, "_get_json", fake_get_json)
    fetchers.fetch_bbc_segments(limit=30)
    assert "limit=10" in seen["url"]


def test_bbc_default_is_within_the_ceiling(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        fetchers, "_get_json", lambda url, **kw: seen.setdefault("url", url) and {"data": []}
    )
    fetchers.fetch_bbc_segments()
    assert f"limit={fetchers.BBC_MAX_LIMIT}" in seen["url"]
    assert fetchers.BBC_MAX_LIMIT <= 10


def test_bbc_drops_segments_missing_artist_or_title(monkeypatch):
    monkeypatch.setattr(
        fetchers,
        "_get_json",
        lambda url, **kw: {
            "data": [
                {"titles": {"primary": "M.I.A.", "secondary": "XXXO"}},
                {"titles": {"primary": "", "secondary": "orphan"}},
                {"titles": {"primary": "Mike D", "secondary": ""}},
            ]
        },
    )
    out = fetchers.fetch_bbc_segments()
    assert out == [{"artist": "M.I.A.", "title": "XXXO", "programme": ""}]
