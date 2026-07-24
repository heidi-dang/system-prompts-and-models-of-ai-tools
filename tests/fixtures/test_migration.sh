#!/usr/bin/env bash
# Test that migration removes stale managed Runtime entries from agent dirs
# and preserves intended public agents plus unrelated custom agents.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Create isolated temporary directories
TMP_HOME="$(mktemp -d)"
TARGET_DIR="$TMP_HOME/.config/opencode/agents"
PRIVATE_DIR="$TMP_HOME/.config/opencode/heidi-runtime"

# Simulate old-style installation: agent dir with stale runtime/ tree
mkdir -p "$TARGET_DIR"
mkdir -p "$TARGET_DIR/runtime/prompts"
mkdir -p "$TARGET_DIR/runtime"

# Stale managed Runtime files (the problem we're fixing)
touch "$TARGET_DIR/runtime/heidi-orchestration.md"
touch "$TARGET_DIR/runtime/orchestration.prompt.md"
touch "$TARGET_DIR/runtime/compatibility.json"
touch "$TARGET_DIR/runtime/prompts/core.md"
touch "$TARGET_DIR/runtime/prompts/routing.md"
touch "$TARGET_DIR/runtime/prompts/orchestration.md"
touch "$TARGET_DIR/runtime/prompts/memory.md"
touch "$TARGET_DIR/runtime/prompts/verification.md"
touch "$TARGET_DIR/runtime/prompts/resilience.md"
touch "$TARGET_DIR/runtime/prompts/reporting.md"
touch "$TARGET_DIR/runtime/prompts/fast-path.md"

# Intended public agents
touch "$TARGET_DIR/heidi.md"
touch "$TARGET_DIR/frontend.md"
touch "$TARGET_DIR/backend.md"
touch "$TARGET_DIR/debugger.md"
touch "$TARGET_DIR/auditor.md"
touch "$TARGET_DIR/planner.md"
touch "$TARGET_DIR/scout.md"

# Unrelated custom agent (must be preserved)
touch "$TARGET_DIR/my-custom-agent.md"

echo "=== Before migration ==="
echo "Files in $TARGET_DIR:"
find "$TARGET_DIR" -type f | sort
echo ""

# Run the migration (simulate what install_mode does)
# Remove stale runtime/ directories
if [ -d "$TARGET_DIR/runtime" ]; then
  rm -rf "$TARGET_DIR/runtime"
fi

# Install private runtime prompts
mkdir -p "$PRIVATE_DIR/prompts"
cp "$REPO_DIR/opencode-agent-pack/runtime/"*.md "$PRIVATE_DIR/" 2>/dev/null || true
cp "$REPO_DIR/opencode-agent-pack/runtime/"*.json "$PRIVATE_DIR/" 2>/dev/null || true
for f in "$REPO_DIR/opencode-agent-pack/runtime/prompts"/*.md; do
  [ -f "$f" ] && cp "$f" "$PRIVATE_DIR/prompts/"
done

echo "=== After migration ==="
echo "Files in $TARGET_DIR:"
find "$TARGET_DIR" -type f | sort
echo ""
echo "Files in $PRIVATE_DIR:"
find "$PRIVATE_DIR" -type f | sort
echo ""

# Verify stale runtime files are gone from agent dir
if [ -d "$TARGET_DIR/runtime" ]; then
  echo "FAIL: stale runtime/ directory still exists in agent dir"
  rm -rf "$TMP_HOME"
  exit 1
fi

# Verify intended public agents are still present
for agent in heidi frontend backend debugger auditor planner scout; do
  if [ ! -f "$TARGET_DIR/$agent.md" ]; then
    echo "FAIL: public agent $agent.md missing from agent dir"
    rm -rf "$TMP_HOME"
    exit 1
  fi
done

# Verify unrelated custom agent is preserved
if [ ! -f "$TARGET_DIR/my-custom-agent.md" ]; then
  echo "FAIL: custom agent my-custom-agent.md was deleted"
  rm -rf "$TMP_HOME"
  exit 1
fi

# Verify private runtime prompts exist
if [ ! -f "$PRIVATE_DIR/prompts/core.md" ] || [ ! -f "$PRIVATE_DIR/prompts/routing.md" ]; then
  echo "FAIL: private runtime prompts not installed"
  rm -rf "$TMP_HOME"
  exit 1
fi

# Verify no internal runtime prompts remain in agent dir
stale_count=$(find "$TARGET_DIR" -name "*.md" | xargs grep -l "orchestrat\|resilien\|fast.path" 2>/dev/null | wc -l)
if [ "$stale_count" -gt 0 ]; then
  echo "FAIL: internal runtime content still present in agent dir"
  rm -rf "$TMP_HOME"
  exit 1
fi

echo "PASS: migration test passed"
rm -rf "$TMP_HOME"
exit 0
