import json

from typer.testing import CliRunner

from crate import seeds, state
from crate.cli import app

runner = CliRunner()


def _init_state():
    state.save_sources(seeds.SEED_SOURCES)
    state.save_signals(state.load_signals())
    state.save_exclusions(state.load_exclusions())
    state.save_taste("# Taste\n\ntest listener\n")


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "crate" in result.output


def test_sources_list_json():
    _init_state()
    result = runner.invoke(app, ["sources", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert any(s["name"] == "NTS" for s in data)


def test_sources_list_type_filter():
    _init_state()
    result = runner.invoke(app, ["sources", "list", "--json", "--type", "reissue-label"])
    data = json.loads(result.stdout)
    assert data and all(s["type"] == "reissue-label" for s in data)


def test_sources_add_and_weight():
    _init_state()
    result = runner.invoke(
        app, ["sources", "add", "Test Digger", "--trust", "0.6", "--type", "individual"]
    )
    assert result.exit_code == 0
    result = runner.invoke(app, ["sources", "weight", "Test Digger", "0.9"])
    assert result.exit_code == 0
    assert state.get_source("Test Digger")["trust"] == 0.9


def test_sources_weight_not_found_exits_2():
    _init_state()
    result = runner.invoke(app, ["sources", "weight", "Nobody", "0.5"])
    assert result.exit_code == 2


def test_sources_ingest_from_stdin():
    _init_state()
    result = runner.invoke(
        app, ["sources", "ingest", "NTS", "--label", "test"], input="Artist - Track\n"
    )
    assert result.exit_code == 0
    from crate.fetchers import load_manual_ingests

    assert "Artist - Track" in load_manual_ingests("NTS")[0]


def test_taste_json():
    _init_state()
    result = runner.invoke(app, ["taste", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "taste_md" in data and "signals" in data


def test_history_empty_exits_2():
    _init_state()
    result = runner.invoke(app, ["history", "list"])
    assert result.exit_code == 2


def test_history_show_json():
    _init_state()
    state.write_playlist_record(
        "2026-07-08",
        {"stamp": "2026-07-08", "thesis": "t", "tracks": [], "dry_run": True},
    )
    result = runner.invoke(app, ["history", "show", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["stamp"] == "2026-07-08"


def test_dig_without_init_fails_cleanly():
    result = runner.invoke(app, ["dig", "--dry-run", "--json"])
    assert result.exit_code == 1
    assert "error" in json.loads(result.stdout)


def test_init_noninteractive(monkeypatch):
    result = runner.invoke(app, ["init", "--skip-spotify", "--skip-interview"])
    assert result.exit_code == 0
    assert state.load_sources()
    assert state.load_taste()


# --- canon ---

def test_canon_list_empty_explains_why_it_starts_empty():
    result = runner.invoke(app, ["canon", "list"])
    assert result.exit_code == 0
    assert "empty" in result.stdout.lower()


def test_canon_list_json_is_a_list():
    result = runner.invoke(app, ["canon", "list", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == []


def test_canon_add_then_list():
    result = runner.invoke(
        app,
        ["canon", "add", "Ethio-jazz", "Mulatu Astatke", "Yekermo Sew",
         "--note", "the template", "--what-it-does", "vibraphone over Amharic modes"],
    )
    assert result.exit_code == 0
    data = json.loads(runner.invoke(app, ["canon", "list", "--json"]).stdout)
    assert data[0]["name"] == "Ethio-jazz"
    assert data[0]["what_it_does"] == "vibraphone over Amharic modes"
    assert data[0]["anchors"][0]["record"] == "Mulatu Astatke — Yekermo Sew"


# --- graph ---

def test_graph_stats_on_an_empty_graph():
    result = runner.invoke(app, ["graph", "stats", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["edges"] == 0


def test_graph_show_unknown_name_exits_2():
    result = runner.invoke(app, ["graph", "show", "Nobody At All"])
    assert result.exit_code == 2


def test_graph_show_walks_from_a_known_node():
    from crate import graph

    graph.add_nodes([
        {"kind": "artist", "name": "Mulatu Astatke"},
        {"kind": "release", "name": "Mulatu Of Ethiopia"},
    ])
    graph.add_edges([{
        "src": "artist:mulatu-astatke", "dst": "release:mulatu-of-ethiopia",
        "kind": "played-on", "asserted_by": "discogs:release/1",
    }])
    result = runner.invoke(app, ["graph", "show", "Mulatu Astatke", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)[0]["name"] == "Mulatu Of Ethiopia"


# --- registry migration ---

def test_sources_migrate_writes_incentive_down():
    stripped = [{k: v for k, v in s.items() if k != "incentive"} for s in seeds.SEED_SOURCES]
    state.save_sources(stripped)
    result = runner.invoke(app, ["sources", "migrate", "--json"])
    assert result.exit_code == 0
    assert len(json.loads(result.stdout)["filled"]) == len(seeds.SEED_SOURCES)
    # Second run is a no-op — the field is on disk now.
    again = runner.invoke(app, ["sources", "migrate", "--json"])
    assert json.loads(again.stdout)["filled"] == []


def test_sources_migrate_before_init_exits_1():
    result = runner.invoke(app, ["sources", "migrate", "--json"])
    assert result.exit_code == 1


def test_sources_list_json_carries_incentive():
    _init_state()
    result = runner.invoke(app, ["sources", "list", "--json"])
    data = json.loads(result.stdout)
    assert all(s.get("incentive") for s in data)
