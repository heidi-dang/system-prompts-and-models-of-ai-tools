#!/usr/bin/env bash
# Mock OpenCode CLI for deterministic CI testing.
# Supports the minimum OpenCode interface used by:
#   - agent.sh: version detection, agent list, debug config
#   - runtime_doctor.py: binary detection, agent discovery, config lookup
set -euo pipefail

MOCK_VERSION="0.1.0-mock"

# Path to this file's config directory
FIXTURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$FIXTURE_DIR/opencode_config"

case "${1:-}" in
  --version|version)
    echo "opencode version $MOCK_VERSION"
    exit 0
    ;;
  agent)
    case "${2:-}" in
      list)
        if [ -d "$CONFIG_DIR/agents" ]; then
          for f in "$CONFIG_DIR/agents"/*.md; do
            [ -f "$f" ] && basename "$f" .md
          done
        fi
        exit 0
        ;;
      *)
        echo "unknown agent subcommand: $2" >&2
        exit 1
        ;;
    esac
    ;;
  debug)
    case "${2:-}" in
      config)
        if [ -f "$CONFIG_DIR/opencode.json" ]; then
          cat "$CONFIG_DIR/opencode.json"
        else
          echo "{}"
        fi
        exit 0
        ;;
      *)
        echo "unknown debug subcommand: $2" >&2
        exit 1
        ;;
    esac
    ;;
  "")
    echo "opencode $MOCK_VERSION"
    exit 0
    ;;
  *)
    echo "unknown command: $*" >&2
    exit 1
    ;;
esac
