#!/usr/bin/env bash
# Install all YouTube Skillbox skills into an agent's skills directory.
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: ./install.sh <skills-directory>"
  echo ""
  echo "  <skills-directory> = the folder where your AI agent discovers"
  echo "  SKILL.md files (created automatically if missing)."
  exit 1
fi

DEST="$1"
SRC="$(cd "$(dirname "$0")" && pwd)/skills"

mkdir -p "$DEST"
cp -r "$SRC"/* "$DEST/"

count=$(find "$SRC" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')
echo "Installed $count skills -> $DEST"
echo "Restart your agent session to pick them up."
