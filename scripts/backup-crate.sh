#!/usr/bin/env bash
# Snapshot ~/.crate. It lives on exactly one machine and nothing else backs it
# up; taste-signals.json and history/ are irreplaceable (see CLAUDE.md).
# The cache is excluded (regenerable, and most of the bytes) and so is
# auth.json — it holds live OAuth tokens, and re-auth is one `crate init`.
set -euo pipefail

CRATE_HOME="${CRATE_HOME:-$HOME/.crate}"
DEST="${CRATE_BACKUP_DIR:-$HOME/dev/backups/crate}"
stamp="$(date +%Y-%m-%dT%H%M%S)"

[ -d "$CRATE_HOME" ] || { echo "no state dir at $CRATE_HOME" >&2; exit 1; }
mkdir -p "$DEST"

# BSD tar (macOS): --exclude before the path, no --warning flags.
tar --exclude='cache' --exclude='auth.json' -czf "$DEST/crate-$stamp.tgz" -C "$(dirname "$CRATE_HOME")" "$(basename "$CRATE_HOME")"

chmod 600 "$DEST/crate-$stamp.tgz"
echo "$DEST/crate-$stamp.tgz"
ls -t "$DEST"/crate-*.tgz | tail -n +11 | xargs -r rm --   # keep the last 10
