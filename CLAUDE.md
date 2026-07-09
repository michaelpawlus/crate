# CRATE — agent notes

CLI agent that builds Spotify playlists via trust networks of human curators
(diggers, reissue labels, radio DJs) instead of similarity scores, and learns
the listener's taste from structured feedback. Philosophy: quality always, no
genres; surprise is the product; a playlist is an argument.

## Commands

```bash
uv sync                 # install
uv run pytest -q        # tests (deterministic core only, no network/agent)
uv run crate --help
```

CLI surface (all read commands support `--json`; exit codes 0/1/2 =
ok/error/not-found):

```
crate init [--skip-spotify] [--skip-interview] [--client-id ...]
crate dig [--brief "..."] [--length N] [--dry-run] [--offline] [--notify] [--json]
crate feedback [stamp] [--quick "..."] [--yes] [--json]
crate taste | crate taste edit
crate sources list|add|weight|ingest
crate history list|show
crate doctor [--json] [--skip-sources]
```

## Architecture

Pipeline: INTENT → SOURCE → TRIANGULATE → SEQUENCE → RESOLVE → PUBLISH
(`src/crate/pipeline/`). SOURCE/TRIANGULATE/SEQUENCE are LLM-agent stages;
RESOLVE/PUBLISH are deterministic — the agent never touches the Spotify API
directly.

- `agent.py` — LLM runtime. Default backend shells out to `claude -p`
  (headless Claude Code, no API key needed); `CRATE_AGENT_BACKEND=api` uses
  the Anthropic API. Prompts are versioned Markdown in `src/crate/prompts/`
  with `{{placeholder}}` substitution; the curator mindset lives in
  `curator-system.md`.
- `state.py` — all state is human-readable files in `~/.crate` (override with
  `CRATE_HOME`); manual edits are authoritative.
- `learning.py` — feedback → source trust weights, stretch budget, exclusions,
  taste.md proposals, drift audit.
- `config.py` — anti-convergence guardrail constants (exploration floor 20%,
  source weight floor 0.1, high-stretch skip discount ⅓). These are
  deliberately constants, NOT state: the learning loop must never tune them.
- `docs/curator-model.md` — the digger playbook the SOURCE agent executes.
- `docs/source-access.md` — verified access methods per source (July 2026).

## Conventions

- Tests must not hit the network or the agent backend; everything under
  `tests/` runs against the deterministic core with `CRATE_HOME` isolated by
  the autouse fixture in `conftest.py`.
- Every track in a playlist must carry provenance (a registry source + why).
  Code that would emit a track without it is a bug, not a style issue.
- On low-confidence Spotify matches: drop, never substitute (karaoke/cover
  pollution). Unresolved tracks go to the unresolved-gems report.
