#!/usr/bin/env bash
# Install active YouTube Skillbox skills into an agent's skills directory.
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

count=0
for skill_dir in "$SRC"/*/; do
  [ -d "$skill_dir" ] || continue
  skill_name="$(basename "$skill_dir")"
  if [ "$skill_name" = "yt-audit" ]; then
    continue
  fi
  cp -r "$skill_dir" "$DEST/"
  count=$((count + 1))
done

if [ ! -f "$DEST/youtube/scripts/ytdata.py" ]; then
  echo "ERROR: shared engine missing at $DEST/youtube/scripts/ytdata.py" >&2
  exit 1
fi

echo "Installed $count active skills -> $DEST"
echo "Shared engine -> $DEST/youtube/scripts/ytdata.py"
echo "Restart your agent session to pick them up."