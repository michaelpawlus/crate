"""CRATE CLI. Plain commands, plain files, pipe-friendly output.

Agent-friendly conventions: `--json` on read commands emits JSON to stdout
(human messages go to stderr); exit codes 0=ok, 1=error, 2=not found;
prompts are skipped when stdin is not a TTY or `--json` is set.
"""

import json
import os
import subprocess
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import __version__, config, seeds, state

app = typer.Typer(
    name="crate",
    help="Playlists dug by trust networks of humans, not similarity scores.",
    no_args_is_help=True,
)
sources_app = typer.Typer(help="Manage the trusted source registry.", no_args_is_help=True)
taste_app = typer.Typer(
    help="Inspect or edit the taste profile.", invoke_without_command=True
)
history_app = typer.Typer(help="Browse past digs.", no_args_is_help=True)
app.add_typer(sources_app, name="sources")
app.add_typer(taste_app, name="taste")
app.add_typer(history_app, name="history")

console = Console(stderr=True)
out = Console()


def _emit_json(data) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _fail(msg: str, code: int = 1, as_json: bool = False):
    if as_json:
        print(json.dumps({"error": msg, "code": code}))
    else:
        console.print(f"[red]error:[/red] {msg}")
    raise typer.Exit(code)


def _interactive() -> bool:
    return sys.stdin.isatty()


@app.callback(invoke_without_command=True)
def _main(version: bool = typer.Option(False, "--version", help="Show version.")):
    if version:
        out.print(f"crate {__version__}")
        raise typer.Exit()


# ---------------------------------------------------------------- init

@app.command()
def init(
    skip_spotify: bool = typer.Option(False, help="Skip Spotify authorization."),
    skip_interview: bool = typer.Option(False, help="Skip the taste interview."),
    client_id: Optional[str] = typer.Option(
        None, help="Spotify app client ID (or set CRATE_SPOTIFY_CLIENT_ID)."
    ),
):
    """Set up ~/.crate: seed sources, Spotify OAuth, taste interview."""
    config.ensure_dirs()

    if not config.sources_path().exists():
        state.save_sources(seeds.SEED_SOURCES)
        console.print(f"✓ Seeded {len(seeds.SEED_SOURCES)} sources → {config.sources_path()}")
    else:
        console.print("✓ sources.yaml already exists (left untouched)")

    if not config.signals_path().exists():
        state.save_signals(state.load_signals())
        console.print(f"✓ Wrote default signals → {config.signals_path()}")
    if not config.exclusions_path().exists():
        state.save_exclusions(state.load_exclusions())

    if not skip_spotify:
        from . import spotify

        cid = client_id or os.environ.get("CRATE_SPOTIFY_CLIENT_ID", "")
        if not cid and _interactive():
            console.print(
                "\n[bold]Spotify setup[/bold] — create an app at "
                "https://developer.spotify.com/dashboard\n"
                f"  redirect URI: [cyan]{config.SPOTIFY_REDIRECT_URI}[/cyan]"
            )
            cid = typer.prompt("Spotify client ID (enter to skip)", default="").strip()
        if cid:
            try:
                spotify.authorize(cid)
                console.print("✓ Spotify authorized")
            except Exception as exc:
                console.print(f"[yellow]Spotify auth failed:[/yellow] {exc}")
        else:
            console.print("→ Skipping Spotify (rerun `crate init` when ready)")

    if not skip_interview and _interactive() and not state.load_taste():
        _taste_interview()
    elif not state.load_taste():
        state.save_taste(seeds.TASTE_TEMPLATE)
        console.print(f"✓ Wrote taste.md template → {config.taste_path()} (edit it!)")

    console.print("\n[bold green]CRATE is ready.[/bold green] Try: crate dig --dry-run")


def _taste_interview() -> None:
    console.print("\n[bold]Taste interview[/bold] — short answers are fine.\n")
    questions = {
        "records": "Name 3-5 records or artists you love, any era, any genre:",
        "surprise": "Describe the last time a song genuinely surprised you — what was it, what did it do?",
        "allergies": "What can't you stand? (sounds, production styles, moods)",
        "context": "When do you actually listen? (commute, cooking, deep work…)",
        "stretch": "How adventurous should this get? (play it safe / one curveball per playlist / take me somewhere weird)",
        "eras": "Any eras or parts of the world you're drawn to — or curious about?",
    }
    answers = {k: typer.prompt(q, default="").strip() for k, q in questions.items()}
    from . import agent

    console.print("\nWriting your taste profile…")
    try:
        prompt = agent.load_prompt("interview", answers_json=json.dumps(answers, indent=1))
        taste = agent.run_agent(prompt).strip() + "\n"
        if taste.startswith("```"):
            taste = "\n".join(l for l in taste.splitlines() if not l.startswith("```")) + "\n"
    except Exception as exc:
        console.print(f"[yellow]Agent unavailable ({exc}); writing template.[/yellow]")
        taste = seeds.TASTE_TEMPLATE + "\n## Interview answers\n\n" + "\n".join(
            f"- **{k}**: {v}" for k, v in answers.items()
        ) + "\n"
    state.save_taste(taste)
    console.print(f"✓ taste.md written → {config.taste_path()}")


# ---------------------------------------------------------------- dig

@app.command()
def dig(
    brief: Optional[str] = typer.Option(None, help='Per-run brief, e.g. "rainy Sunday, instrumental-leaning".'),
    length: Optional[int] = typer.Option(None, help=f"Playlist length (default {config.DEFAULT_LENGTH})."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Stop before Spotify: output Markdown only."),
    offline: bool = typer.Option(False, help="No agent web research; fetched material and manual ingests only."),
    notify: bool = typer.Option(False, help="Print a one-line summary to stdout (cron/ntfy-friendly)."),
    as_json: bool = typer.Option(False, "--json", help="Emit the playlist record as JSON."),
):
    """Dig a playlist: INTENT → SOURCE → TRIANGULATE → SEQUENCE → RESOLVE → PUBLISH."""
    from .pipeline import intent, publish, resolve, sequence, source, triangulate

    if not config.sources_path().exists():
        _fail("not initialized — run `crate init` first", as_json=as_json)
    config.ensure_dirs()

    run_spec = intent.build_run_spec(brief, length)
    if brief and "reset run" in brief.lower():
        run_spec["stretch_budget"] = 1.0  # drift-audit reset: max range

    try:
        console.print("[bold]SOURCE[/bold] — digging the registry…")
        candidates, picked = source.run_source_stage(run_spec, dry_run_offline=offline)
        picked_names = [s["name"] for s in picked]
        console.print(f"  {len(candidates)} candidates from: {', '.join(picked_names)}")

        top_keys: set[str] = set()
        if not dry_run:
            try:
                from . import spotify

                top_keys = {
                    state.track_key(t["artist"], t["track"]) for t in spotify.top_tracks()
                }
            except Exception:
                pass  # freshness penalty is optional

        console.print("[bold]TRIANGULATE[/bold] — scoring…")
        selection = triangulate.run_triangulate_stage(candidates, run_spec, top_keys)

        console.print("[bold]SEQUENCE[/bold] — building the arc…")
        sequenced = sequence.run_sequence_stage(selection, run_spec)

        resolved, unresolved = sequenced["tracks"], []
        if not dry_run:
            console.print("[bold]RESOLVE[/bold] — matching Spotify catalog…")
            resolved, unresolved = resolve.run_resolve_stage(sequenced["tracks"])
            console.print(f"  {len(resolved)} resolved, {len(unresolved)} unresolved gems")

        console.print("[bold]PUBLISH[/bold]…")
        record = publish.run_publish_stage(
            run_spec, sequenced, resolved, unresolved, picked_names, dry_run
        )
    except Exception as exc:
        _fail(str(exc), as_json=as_json)

    if as_json:
        _emit_json(record)
    elif notify:
        n = len(record["tracks"])
        url = record.get("playlist_url") or record["liner_notes_path"]
        print(f"CRATE {record['stamp']}: {n} tracks — {record['thesis']} — {url}")
    else:
        out.print(open(record["liner_notes_path"]).read())
        if record.get("playlist_url"):
            out.print(f"\n▶ {record['playlist_url']}")
        out.print(f"\nLiner notes: {record['liner_notes_path']}")

    drift = None
    try:
        from . import learning

        drift = learning.drift_check()
    except Exception:
        pass
    if drift and drift["drifting"]:
        console.print(f"[yellow]⚠ Drift audit:[/yellow] {drift['recommendation']}")


# ---------------------------------------------------------------- feedback

@app.command()
def feedback(
    playlist: Optional[str] = typer.Argument(None, help="Playlist date stamp (default: latest)."),
    quick: Optional[str] = typer.Option(None, "--quick", help='Free-text feedback: "loved 3,7,11; skip 5; too mellow overall".'),
    yes: bool = typer.Option(False, "--yes", "-y", help="Accept the proposed taste.md update without prompting."),
    as_json: bool = typer.Option(False, "--json", help="Emit the parsed feedback and changes as JSON."),
):
    """Give feedback on a playlist — interactive walk, or --quick free text."""
    from . import feedback as fb
    from . import learning

    record = (
        state.load_playlist_record(playlist) if playlist else state.latest_playlist_record()
    )
    if not record:
        _fail("no playlists in history yet — run `crate dig` first", code=2, as_json=as_json)

    if quick:
        try:
            records = fb.parse_quick(quick, record)
        except Exception as exc:
            _fail(f"could not parse feedback: {exc}", as_json=as_json)
    elif _interactive() and not as_json:
        records = fb.interactive_session(record)
    else:
        _fail("no --quick text given and not a TTY", as_json=as_json)

    state.append_feedback(record["stamp"], records)
    changes = learning.apply_feedback(records)

    taste_updated = False
    try:
        new_taste, diff = learning.propose_taste_update(records)
        if diff.strip():
            if yes or not _interactive() or as_json:
                state.save_taste(new_taste)
                taste_updated = True
            else:
                console.print("\n[bold]Proposed taste.md update:[/bold]")
                console.print(diff)
                if typer.confirm("Accept?", default=True):
                    state.save_taste(new_taste)
                    taste_updated = True
                else:
                    state.write_history_file(
                        record["stamp"], "taste-proposal.md", new_taste
                    )
                    console.print("Saved proposal to history/ instead.")
    except Exception as exc:
        console.print(f"[yellow]taste.md update skipped:[/yellow] {exc}")

    summary = {
        "playlist": record["stamp"],
        "records_written": len(records),
        "changes": changes,
        "taste_md_updated": taste_updated,
    }
    if as_json:
        _emit_json(summary)
    else:
        console.print(
            f"\n✓ {len(records)} feedback records → history/{record['stamp']}-feedback.jsonl"
        )
        sb = changes.get("stretch_budget", {})
        if sb and sb.get("old") != sb.get("new"):
            console.print(f"  stretch budget: {sb['old']} → {sb['new']}")
        if changes.get("exclusions_added"):
            console.print(f"  never again: {', '.join(changes['exclusions_added'])}")


# ---------------------------------------------------------------- taste

@taste_app.callback()
def taste_show(
    ctx: typer.Context,
    as_json: bool = typer.Option(False, "--json", help="Emit taste.md + signals as JSON."),
):
    """Print the current taste profile and key learned signals."""
    if ctx.invoked_subcommand is not None:
        return
    taste = state.load_taste()
    if not taste:
        _fail("no taste profile yet — run `crate init`", code=2, as_json=as_json)
    signals = state.load_signals()
    if as_json:
        _emit_json({"taste_md": taste, "signals": signals})
        return
    out.print(taste)
    out.print("\n--- key signals ---")
    out.print(f"stretch budget:    {signals['stretch_budget']}")
    out.print(f"familiarity ratio: {signals['familiarity_ratio']}")
    out.print(f"playlists:         {signals.get('playlists_generated', 0)}")
    out.print(f"feedback sessions: {signals.get('feedback_sessions', 0)}")


@taste_app.command("edit")
def taste_edit():
    """Open taste.md in $EDITOR."""
    editor = os.environ.get("EDITOR", "nano")
    if not config.taste_path().exists():
        state.save_taste(seeds.TASTE_TEMPLATE)
    subprocess.run([editor, str(config.taste_path())])


# ---------------------------------------------------------------- sources

@sources_app.command("list")
def sources_list(
    as_json: bool = typer.Option(False, "--json"),
    type_filter: Optional[str] = typer.Option(None, "--type", help="Filter by source type."),
):
    """List the trusted source registry with weights."""
    sources = state.load_sources()
    if type_filter:
        sources = [s for s in sources if s.get("type") == type_filter]
    if as_json:
        _emit_json(sources)
        return
    table = Table(title="Trusted sources")
    for col in ("name", "type", "access", "trust", "feedback"):
        table.add_column(col)
    for s in sorted(sources, key=lambda x: -x.get("trust", 0)):
        table.add_row(
            s["name"], s.get("type", ""), s.get("access", ""),
            f"{s.get('trust', 0.5):.2f}", str(s.get("feedback_count", 0)),
        )
    out.print(table)


@sources_app.command("add")
def sources_add(
    name: str,
    type: str = typer.Option("individual", help="radio|reissue-label|publication|list-community|individual"),
    access: str = typer.Option("manual", help="api|rss|web|scrape|manual"),
    endpoint: str = typer.Option("", help="URL / feed / API base."),
    trust: float = typer.Option(0.7, min=0.1, max=1.0),
    notes: str = typer.Option(""),
):
    """Add a source to the registry."""
    sources = state.load_sources()
    if any(s["name"].lower() == name.lower() for s in sources):
        _fail(f"source '{name}' already exists")
    sources.append(
        {"name": name, "type": type, "access": access, "endpoint": endpoint,
         "trust": trust, "feedback_count": 0, "notes": notes}
    )
    state.save_sources(sources)
    console.print(f"✓ Added {name} (trust {trust})")


@sources_app.command("weight")
def sources_weight(name: str, trust: float = typer.Argument(..., min=0.1, max=1.0)):
    """Manually set a source's trust weight."""
    sources = state.load_sources()
    for s in sources:
        if s["name"].lower() == name.lower():
            s["trust"] = trust
            state.save_sources(sources)
            console.print(f"✓ {s['name']} trust → {trust}")
            return
    _fail(f"source '{name}' not found", code=2)


@sources_app.command("ingest")
def sources_ingest(
    name: str,
    file: Optional[typer.FileText] = typer.Option(None, help="File with a tracklist (default: stdin)."),
    label: str = typer.Option("", help="What this is, e.g. 'NTS 2026-07-01 episode'."),
):
    """Manually ingest a tracklist/list for a source — the path that always works.

    Example: pbpaste | crate sources ingest "Zach Cowie" --label "IG mix 07/26"
    """
    from . import fetchers

    if state.get_source(name) is None:
        _fail(f"source '{name}' not in registry — `crate sources add` it first", code=2)
    text = file.read() if file else sys.stdin.read()
    if not text.strip():
        _fail("no content provided")
    path = fetchers.ingest_manual(name, text, label)
    console.print(f"✓ Ingested → {path}")


# ---------------------------------------------------------------- history

@history_app.command("list")
def history_list(as_json: bool = typer.Option(False, "--json")):
    """List past digs."""
    records = [state.load_playlist_record(p) for p in state.list_playlist_records()]
    if as_json:
        _emit_json(
            [
                {"stamp": r["stamp"], "thesis": r["thesis"], "tracks": len(r["tracks"]),
                 "dry_run": r.get("dry_run", False), "playlist_url": r.get("playlist_url")}
                for r in records
            ]
        )
        return
    if not records:
        console.print("No digs yet.")
        raise typer.Exit(2)
    for r in records:
        marker = "dry" if r.get("dry_run") else "▶"
        out.print(f"{r['stamp']}  [{marker}]  {len(r['tracks'])} tracks — {r['thesis']}")


@history_app.command("show")
def history_show(
    stamp: Optional[str] = typer.Argument(None, help="Date stamp (default: latest)."),
    as_json: bool = typer.Option(False, "--json"),
):
    """Show one dig's full record (tracks, provenance, rationale)."""
    record = state.load_playlist_record(stamp) if stamp else state.latest_playlist_record()
    if not record:
        _fail("not found", code=2, as_json=as_json)
    if as_json:
        _emit_json(record)
        return
    notes = config.history_dir() / f"{record['stamp']}-liner-notes.md"
    out.print(notes.read_text() if notes.exists() else json.dumps(record, indent=2))


# ---------------------------------------------------------------- doctor

@app.command()
def doctor(
    as_json: bool = typer.Option(False, "--json"),
    skip_sources: bool = typer.Option(False, help="Skip live source health checks."),
):
    """Check auth, agent backend, source health, cache, and taste drift."""
    from . import doctor as doc

    report = doc.run_checks(check_sources=not skip_sources)
    if as_json:
        _emit_json(report)
        raise typer.Exit(0 if report["ok"] else 1)
    for name, check in report["checks"].items():
        icon = "[green]✓[/green]" if check.get("ok") else "[red]✗[/red]"
        detail = check.get("detail")
        if isinstance(detail, dict) and "detail" in detail:
            detail = detail["detail"]
        if isinstance(detail, dict):
            out.print(f"{icon} {name}:")
            for k, v in detail.items():
                out.print(f"    {k}: {v}")
        else:
            out.print(f"{icon} {name}: {detail}")
    raise typer.Exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    app()
