#!/usr/bin/env bash
# Link every <project>/<skill> folder of this repository into ~/.claude/skills.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
DEST=${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}
mkdir -p "$DEST"

for skill in "$HERE"/*/*/SKILL.md; do
  dir=$(dirname "$skill")
  name=$(basename "$dir")
  link="$DEST/$name"
  if [ -e "$link" ] && [ ! -L "$link" ]; then
    printf 'skip %s: %s is a real folder, not a link\n' "$name" "$link" >&2
    continue
  fi
  ln -sfn "$dir" "$link"
  printf 'linked %s -> %s\n' "$link" "$dir"
done
