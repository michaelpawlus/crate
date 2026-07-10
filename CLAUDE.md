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

## Spotify API notes (learned 2026-07-09, first live publish)

Spotify's February 2026 Web API changes broke the endpoints the original spec
was written against. Current working surface (all in `spotify.py`):

- Create playlist: `POST /me/playlists`. The documented
  `POST /users/{id}/playlists` returns a bare 403 for development-mode apps
  created after the 2025 policy change.
- Add tracks: `POST /playlists/{id}/items`. The old `/playlists/{id}/tracks`
  endpoint was **removed** Feb 2026 — bare 403, no migration hint in the body.
- A 403 with just `"Forbidden"` (no "insufficient scope" message) usually means
  a removed/restricted endpoint, not an auth problem. Diagnose by probing
  endpoint variants with the stored token before touching OAuth.
- The `public` field on GET playlist is unreliable (reads `true` for
  API-created playlists regardless); `public: false` at create time does work.
- WSL2 auth flow: `webbrowser.open` fails (gio error) and long URLs truncate in
  the terminal. Working pattern: run `spotify.authorize()` in a background
  process, grep the URL from its output, hand it to the user as one clickable
  markdown link. Redirect URI is `http://127.0.0.1:8765/callback` (loopback IP
  required; Spotify rejects `localhost`).

## Conventions

- Tests must not hit the network or the agent backend; everything under
  `tests/` runs against the deterministic core with `CRATE_HOME` isolated by
  the autouse fixture in `conftest.py`.
- Every track in a playlist must carry provenance (a registry source + why).
  Code that would emit a track without it is a bug, not a style issue.
- On low-confidence Spotify matches: drop, never substitute (karaoke/cover
  pollution). Unresolved tracks go to the unresolved-gems report.
