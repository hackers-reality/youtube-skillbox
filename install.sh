#!/usr/bin/env bash
# Install all YouTube Skillbox skills into OpenCode's global skills directory.
set -euo pipefail

DEST="${HOME}/.config/opencode/skills"
SRC="$(cd "$(dirname "$0")" && pwd)/skills"

mkdir -p "$DEST"
cp -r "$SRC"/* "$DEST/"

count=$(find "$SRC" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')
echo "Installed $count skills -> $DEST"
echo "Restart your agent session to pick them up."
