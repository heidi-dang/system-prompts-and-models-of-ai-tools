#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_SRC="$SCRIPT_DIR/opencode-agent-pack/agents"
AGENT_NAMES=(heidi frontend backend debugger auditor planner)

usage() {
  cat <<EOF
Usage: $0 [--global | --project | --both | --check]

Install OpenCode Heidi agent pack.

  --global   Install into OPENCODE_CONFIG_DIR or ~/.config/opencode/agents (default)
  --project  Install into .opencode/agents in the current directory
  --both     Install into both global and project directories
  --check    Print diagnostic information without installing

If no flag is given, --global is assumed.
EOF
  exit 0
}

MODE="global"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --global) MODE="global"; shift ;;
    --project) MODE="project"; shift ;;
    --both) MODE="both"; shift ;;
    --check) MODE="check"; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

if [ ! -d "$AGENT_SRC" ]; then
  echo "Error: agent source directory not found at $AGENT_SRC"
  echo "Run this script from the repo root."
  exit 1
fi

# --- check mode ---
if [ "$MODE" = "check" ]; then
  CONFIG_DIR="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"
  echo "=== OpenCode Agent Pack Diagnostics ==="
  echo "HOME=$HOME"
  echo "OPENCODE_CONFIG_DIR=${OPENCODE_CONFIG_DIR:-}"
  echo "Global target: $CONFIG_DIR/agents"
  echo "Project target: $(pwd)/.opencode/agents"
  echo ""
  echo "Source agents:"
  for agent in "${AGENT_NAMES[@]}"; do
    src="$AGENT_SRC/$agent.md"
    if [ -f "$src" ]; then
      echo "  $src"
    else
      echo "  $src (MISSING)"
    fi
  done
  echo ""
  echo "Installed agents (global):"
  if [ -d "$CONFIG_DIR/agents" ]; then
    for f in "$CONFIG_DIR/agents"/*.md; do
      [ -f "$f" ] && echo "  $f"
    done
  else
    echo "  (directory does not exist)"
  fi
  echo ""
  echo "Installed agents (project):"
  if [ -d "$(pwd)/.opencode/agents" ]; then
    for f in "$(pwd)/.opencode/agents"/*.md; do
      [ -f "$f" ] && echo "  $f"
    done
  else
    echo "  (directory does not exist)"
  fi
  echo ""
  echo "Agent frontmatter (first 12 lines):"
  for agent in "${AGENT_NAMES[@]}"; do
    src="$AGENT_SRC/$agent.md"
    if [ -f "$src" ]; then
      echo "--- $agent.md ---"
      head -12 "$src"
      echo ""
    fi
  done
  exit 0
fi

# --- install mode ---
install_to() {
  local target="$1"
  mkdir -p "$target"
  TIMESTAMP=$(date +%Y%m%d-%H%M%S)
  for agent in "${AGENT_NAMES[@]}"; do
    src="$AGENT_SRC/$agent.md"
    dst="$target/$agent.md"
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
    dst="$target/$agent.md"
    if [ -f "$dst" ]; then
      echo "  $dst"
    fi
  done
}

CONFIG_DIR="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"

case "$MODE" in
  global)
    install_to "$CONFIG_DIR/agents"
    ;;
  project)
    install_to "$(pwd)/.opencode/agents"
    ;;
  both)
    install_to "$CONFIG_DIR/agents"
    echo ""
    install_to "$(pwd)/.opencode/agents"
    ;;
esac

echo ""
echo "Done. Official OpenCode build and plan agents were not modified."
echo ""
echo "If OpenCode is already open, start a new OpenCode session from the same user/project so the UI reloads custom agents."
