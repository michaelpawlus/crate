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
- Redirect URI is `http://127.0.0.1:8765/callback` — the loopback IP is
  required, Spotify rejects `localhost`.
- Auth flow on macOS: `webbrowser.open` works directly (it resolves to
  `MacOSXOSAScript`), so `crate init` opens the consent page itself and the
  local callback server on port 8765 catches the code. **The WSL2 workaround
  that used to live here is obsolete** — on that host `webbrowser.open` failed
  with a gio error and long URLs truncated in the terminal, so the flow had to
  be run in a background process with the URL grepped out of its output and
  handed over as a markdown link. Don't reach for that on this machine.

## Conventions

- Tests must not hit the network or the agent backend; everything under
  `tests/` runs against the deterministic core with `CRATE_HOME` isolated by
  the autouse fixture in `conftest.py`.
- Every track in a playlist must carry provenance (a registry source + why).
  Code that would emit a track without it is a bug, not a style issue.
- On low-confidence Spotify matches: drop, never substitute (karaoke/cover
  pollution). Unresolved tracks go to the unresolved-gems report.

## Environment (this machine)

Migrated from WSL2 to macOS (Apple Silicon) on 2026-07-29. Written for whoever
does this next.

**Layout**

| What | Where |
|---|---|
| Repo | `~/dev/projects/crate` |
| State | `~/.crate` (override with `CRATE_HOME`) |
| `crate` on `PATH` | `~/.local/bin/crate` → symlink into this repo's `.venv/bin/crate` |

Never put the repo under `~/Documents` or `~/Desktop` — both are iCloud-synced
by default, and iCloud and git corrupt each other.

**Toolchain — uv only, never pip**

```bash
uv sync --locked     # rebuild .venv from uv.lock; --locked is what CI runs
uv run pytest -q
uv run ruff check .
```

Python is pinned to **3.11** in `.python-version`, which is also
`requires-python`'s floor, so CI tests the declared minimum and local runs agree
with it by construction. uv would otherwise pick the newest interpreter present
(3.14 is installed here). Nothing currently proves 3.12+.

`crate` on `PATH` is a symlink to `.venv/bin/crate`, deliberately **not**
`uv tool install`: a separate tool env re-resolves dependencies outside
`uv.lock`, and with `typer>=0.12` declared against a 0.26.8 lock that means the
whole CLI surface would run on an untested typer. Tradeoff: `crate` breaks if
`.venv` is deleted — `uv sync` restores it.

**Environment variables** — read from the shell; there is no `.env` and nothing
calls `load_dotenv()`, so these belong in `~/.zshenv` (→ `~/dev/dotfiles/zsh/.zshenv`),
not `~/.zshrc`. zsh sources `.zshrc` only for *interactive* shells, and agent
tooling invokes `crate` non-interactively.

| Var | Required | Default | Notes |
|---|---|---|---|
| `CRATE_SPOTIFY_CLIENT_ID` | for `crate init` | — | After first auth it is also stored in `~/.crate/auth.json`, so it is only needed to re-authorize |
| `CRATE_HOME` | no | `~/.crate` | The autouse test fixture points this at a tmpdir |
| `CRATE_AGENT_BACKEND` | no | `claude-cli` | `api` switches to the Anthropic API |
| `CRATE_MODEL` | no | CLI default / `claude-sonnet-5` on `api` | |
| `ANTHROPIC_API_KEY` | only if backend is `api` | — | The default `claude-cli` backend needs no key |
| `OBSIDIAN_VAULT_PATH` | no | unset | Mirrors liner notes into `<vault>/crate/`. Already set to `~/dev/vault` |
| `EDITOR` | no | `nano` | Used by `crate taste edit` |

**Machine-local, not in git**

| Item | Where | If missing |
|---|---|---|
| Spotify OAuth tokens | `~/.crate/auth.json` (mode 0600) | Every Spotify call raises `NotAuthenticated`; re-run `crate init` |
| Source registry | `~/.crate/sources.yaml` | `crate doctor` reports uninitialized; `crate init` reseeds from `seeds.py` |
| Taste profile | `~/.crate/taste.md` | Regenerable via the `crate init` interview, but the *learned* version is not |
| Learned signals | `~/.crate/taste-signals.json` | **Irreplaceable.** Source trust weights, stretch budget, mood priors — the accumulated result of every feedback session |
| Playlist history | `~/.crate/history/` | **Irreplaceable.** Every past playlist, liner notes, and feedback log |
| Exclusions | `~/.crate/exclusions.json` | Freshness dedup resets; previously-used tracks can repeat |

`~/.crate` did not survive the migration and was rebuilt from scratch on
2026-07-29 — the WSL2 box was gone before it was copied. Everything marked
irreplaceable above started over at zero. **`~/.crate` now exists on exactly one
machine and nothing backs it up.** It is not large; back it up before it
represents months of feedback again.

**Traps specific to this host**

- `_mirror_to_obsidian` (`pipeline/publish.py`) returns silently if
  `OBSIDIAN_VAULT_PATH` is unset or not a directory — a dig still exits 0 with no
  vault note written. That var is set in `~/.zshenv` for exactly this reason;
  the same class of silent degradation is documented there for beacon.
- `state.now_iso()` returns **UTC** and is currently called by nothing.
  `today_stamp()` and `intent.build_run_spec`'s `weekday` are **local**, and
  `signals.mood_priors` is keyed by that local weekday. Mixing the two would
  file a late-evening dig under tomorrow. If you need a timestamp, match the
  local-civil-date semantics rather than reaching for `now_iso()`. `DTZ011` is
  ignored in `pyproject.toml` for this reason. This was invisible on WSL2, whose
  clock ran UTC.
- Three `api`-tier sources are currently dead, confirmed by `crate doctor` on
  2026-07-29: **NTS** (404 — unofficial endpoint moved), **BBC 6 Music** (400 —
  request shape no longer accepted), and **r/listentothis** (403 — Reddit
  rejects generic user agents; needs a real `User-Agent` header, not a different
  network). `crate doctor` exits 1 whenever any source is dead, so a non-zero
  exit does not mean the install is broken. `fetchers.gather_source_material`
  swallows these by design — a dead source must never kill a dig — so digs still
  run, just with a smaller pool.
- `docs/source-access.md` was originally audited from WSL2 behind **datacenter
  egress**. That turned out not to matter: the 2026-07-29 re-check found no
  source helped by residential egress and no failure caused by blocking. When a
  source fails here, **suspect endpoint drift or client headers before egress** —
  a 4xx means the request arrived.
- Homebrew is at `/opt/homebrew` on Apple Silicon, not `/usr/local`; APFS is
  case-insensitive where ext4 was not; `sed`/`date`/`stat`/`readlink` are BSD
  and take different flags than the GNU versions.
- No scheduled job. `crate dig` has always been run by hand — there is no cron
  entry to port and no launchd plist. If you add one, note that launchd jobs get
  no interactive shell, which is the other reason the env vars live in
  `~/.zshenv`.
