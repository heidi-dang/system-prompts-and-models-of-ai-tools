#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_SRC="$SCRIPT_DIR/opencode-agent-pack/agents"
AGENT_NAMES=(heidi frontend backend debugger auditor planner)

usage() {
  cat <<EOF
Usage: $0 [--global | --project]

Install OpenCode Heidi agent pack.

  --global   Install into OPENCODE_CONFIG_DIR or ~/.config/opencode/agents (default)
  --project  Install into .opencode/agents in the current directory

If no flag is given, --global is assumed.
EOF
  exit 0
}

MODE="global"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --global) MODE="global"; shift ;;
    --project) MODE="project"; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

if [ ! -d "$AGENT_SRC" ]; then
  echo "Error: agent source directory not found at $AGENT_SRC"
  echo "Run this script from the repo root."
  exit 1
fi

if [ "$MODE" = "project" ]; then
  TARGET_DIR=".opencode/agents"
else
  CONFIG_DIR="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"
  TARGET_DIR="$CONFIG_DIR/agents"
fi

mkdir -p "$TARGET_DIR"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)

for agent in "${AGENT_NAMES[@]}"; do
  src="$AGENT_SRC/$agent.md"
  dst="$TARGET_DIR/$agent.md"

  if [ ! -f "$src" ]; then
    echo "Warning: source file $src not found, skipping $agent"
    continue
  fi

  if [ -f "$dst" ]; then
    backup="$dst.bak.$TIMESTAMP"
    cp "$dst" "$backup"
    echo "Backed up existing $dst -> $backup"
  fi

  cp "$src" "$dst"
done

echo ""
echo "Installed agents:"
for agent in "${AGENT_NAMES[@]}"; do
  dst="$TARGET_DIR/$agent.md"
  if [ -f "$dst" ]; then
    echo "  $dst"
  fi
done
echo ""
echo "Done. Official OpenCode build and plan agents were not modified."
