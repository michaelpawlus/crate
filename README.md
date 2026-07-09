# CRATE

**Playlists dug by trust networks of humans, not similarity scores.**

CRATE is a CLI agent that builds Spotify playlists the way an obsessive human
curator would — by following trust networks of diggers, reissue labels, radio
DJs, and liner notes rather than streaming-similarity patterns — and that
learns your taste from structured feedback after every playlist.

**Quality always, no genres.**

## How it works

```
crate dig
  1. INTENT      read brief + taste profile
  2. SOURCE      agentic research across a trusted-source registry
  3. TRIANGULATE score candidates (provenance, cross-source hits, fit, stretch)
  4. SEQUENCE    arc-aware ordering — a playlist is an argument
  5. RESOLVE     match to Spotify URIs (drop, never substitute, on low confidence)
  6. PUBLISH     create the playlist + write liner notes with full provenance
  7. LOG         record everything for the feedback loop
```

Every track is traceable to at least one trusted human source — an NTS
episode, a Numero Group reissue, a Bandcamp Daily feature, a Discogs credit
chain. Tracks that appear independently in two unrelated sources get the
strongest boost. Tracks the agent can't write one honest sentence of
conviction about get cut.

The system learns from feedback (`crate feedback`) but is built to never
collapse into a similarity engine:

- **Exploration floor:** ≥20% of every playlist comes from sources with no
  feedback history. Hard-coded, not tunable.
- High-stretch skips carry ⅓ the negative weight of comfort-zone skips.
- Source rotation: never the same source set two runs in a row.
- A drift audit every 8 playlists checks that diversity isn't contracting.

## Install

Requires Python ≥3.11 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/michaelpawlus/crate
cd crate
uv tool install .        # or: uv sync && uv run crate ...
```

### Agent backend

The SOURCE/TRIANGULATE/SEQUENCE stages are LLM work. By default CRATE invokes
the [Claude Code](https://claude.com/claude-code) CLI headlessly (`claude -p`),
so a Claude subscription covers it with no API key. Alternatively:

```bash
export CRATE_AGENT_BACKEND=api        # use the Anthropic API instead
export ANTHROPIC_API_KEY=sk-ant-...
uv tool install '.[api]'
```

### Spotify setup

1. Create an app at <https://developer.spotify.com/dashboard>
2. Add redirect URI: `http://127.0.0.1:8765/callback`
3. Run `crate init` and paste the client ID (or set `CRATE_SPOTIFY_CLIENT_ID`)

## Usage

```bash
crate init                          # seed sources, Spotify OAuth, taste interview
crate dig --dry-run                 # full dig, Markdown output only (no Spotify)
crate dig --brief "rainy Sunday, instrumental-leaning"
crate feedback                      # interactive track-by-track session
crate feedback --quick "loved 3,7,11; skip 5; too mellow overall"
crate taste                         # current taste.md + learned signals
crate taste edit                    # open taste.md in $EDITOR
crate sources list                  # the trusted-source registry with weights
crate sources ingest "NTS" < tracklist.txt   # manual ingest — always works
crate history list
crate doctor                        # auth, agent, source health, drift check
```

Read commands support `--json` (JSON to stdout, human messages to stderr).
Exit codes: 0 success, 1 error, 2 not found.

Scheduling is deliberately your problem: put `crate dig --notify` in cron.

```cron
0 7 * * 5 crate dig --notify   # a new crate every Friday morning
```

## State

Everything lives in `~/.crate/` as human-readable files you can edit by hand
(manual edits are authoritative):

```
~/.crate/
  sources.yaml          # trusted source registry with tunable weights
  taste.md              # narrative taste profile — prose first, numbers second
  taste-signals.json    # learned parameters (stretch budget, familiarity…)
  exclusions.json       # never-again artists/tracks + freshness history
  history/              # per-dig: playlist record, liner notes, feedback,
                        #   unresolved-gems report
  cache/                # cached fetches + manual ingests
```

## Docs

- [docs/curator-model.md](docs/curator-model.md) — the digger playbook the agent executes
- [docs/source-access.md](docs/source-access.md) — verified access methods per source
- [docs/spec.md](docs/spec.md) — the original build spec

## License

MIT
