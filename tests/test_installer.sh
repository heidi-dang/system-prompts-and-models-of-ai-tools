#!/usr/bin/env bash
# Comprehensive installer test suite.
# Runs in isolated temp directories - does not modify real config.
set -uo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
TEST_ROOT="$(mktemp -d /tmp/opencode-installer-test-XXXXXX)"
trap 'rm -rf "$TEST_ROOT"' EXIT

PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); }
fail() { echo "FAIL: $*"; FAIL=$((FAIL + 1)); }

OUTDIR="$TEST_ROOT/outputs"
mkdir -p "$OUTDIR"

# Helper to run a command and capture its output
run_checked() {
  local name="$1"
  shift
  "$@" > "$OUTDIR/$name.stdout" 2> "$OUTDIR/$name.stderr" || true
}

summary() {
  echo ""
  echo "=========================================="
  echo "Installer tests: $PASS passed, $FAIL failed"
  echo "=========================================="
  [ "$FAIL" -eq 0 ]
}

# ------------------------------------------------------------------
echo "=== 1. Bash syntax check ==="
bash -n agent.sh && pass || fail "bash syntax"

# ------------------------------------------------------------------
echo "=== 2. ShellCheck ==="
if command -v shellcheck >/dev/null 2>&1; then
  shellcheck agent.sh && pass || fail "shellcheck"
else
  echo "  (shellcheck not available, skipping)"
  pass
fi

# ------------------------------------------------------------------
echo "=== 3. --version works ==="
run_checked "version" bash agent.sh --version
grep -q "Heidi OpenCode Agent Pack" "$OUTDIR/version.stdout" && pass || fail "--version"

# ------------------------------------------------------------------
echo "=== 4. Unknown option exits non-zero ==="
set +e
bash agent.sh --bogus-option > /dev/null 2>&1
RC=$?
set -euo pipefail 2>/dev/null || true
[ "$RC" -ne 0 ] && pass || fail "unknown option should fail"

# ------------------------------------------------------------------
echo "=== 5. Global install creates all seven agent files ==="
export OPENCODE_CONFIG_DIR="$TEST_ROOT/global"
mkdir -p "$OPENCODE_CONFIG_DIR"
run_checked "global_install" bash agent.sh --global
COUNT=0
for a in heidi frontend backend debugger auditor planner scout; do
  [ -f "$OPENCODE_CONFIG_DIR/agents/$a.md" ] && COUNT=$((COUNT + 1))
done
[ "$COUNT" -eq 7 ] && pass || fail "global install: $COUNT/7 agents"

# ------------------------------------------------------------------
echo "=== 6. Project install creates all seven project agent files ==="
PROJ_DIR="$TEST_ROOT/project"
mkdir -p "$PROJ_DIR"
cp agent.sh "$PROJ_DIR/"
cp -r opencode-agent-pack "$PROJ_DIR/"
run_checked "project_install" bash -c "cd '$PROJ_DIR' && bash agent.sh --project"
COUNT=0
for a in heidi frontend backend debugger auditor planner scout; do
  [ -f "$PROJ_DIR/.opencode/agents/$a.md" ] && COUNT=$((COUNT + 1))
done
[ "$COUNT" -eq 7 ] && pass || fail "project install: $COUNT/7 agents"

# ------------------------------------------------------------------
echo "=== 7. --config-global installs files and writes valid config ==="
export OPENCODE_CONFIG_DIR="$TEST_ROOT/cfg_global"
mkdir -p "$OPENCODE_CONFIG_DIR"
run_checked "cfg_global" bash agent.sh --config-global
COUNT=0
for a in heidi frontend backend debugger auditor planner scout; do
  [ -f "$OPENCODE_CONFIG_DIR/agents/$a.md" ] && COUNT=$((COUNT + 1))
done
[ "$COUNT" -eq 7 ] || fail "--config-global: $COUNT/7 agents"
python3 -c "
import json
cfg = json.load(open('$OPENCODE_CONFIG_DIR/opencode.json'))
assert 'agent' in cfg, 'missing agent key'
assert 'agents' not in cfg, 'has deprecated agents key'
assert '\$schema' in cfg, 'missing schema'
heidi_agents = {'heidi','frontend','backend','debugger','auditor','planner','scout'}
assert heidi_agents.issubset(cfg['agent']), 'missing agents'
for name in heidi_agents:
    prompt = cfg['agent'][name].get('prompt', '')
    assert prompt.startswith('{file:'), f'{name}: bad prompt {prompt}'
print('config OK')
" && pass || fail "--config-global config validation"

# ------------------------------------------------------------------
echo "=== 8. --config-project installs files and writes valid config ==="
PROJ2="$TEST_ROOT/cfg_project"
mkdir -p "$PROJ2"
cp agent.sh "$PROJ2/"
cp -r opencode-agent-pack "$PROJ2/"
run_checked "cfg_project" bash -c "cd '$PROJ2' && bash agent.sh --config-project"
COUNT=0
for a in heidi frontend backend debugger auditor planner scout; do
  [ -f "$PROJ2/.opencode/agents/$a.md" ] && COUNT=$((COUNT + 1))
done
[ "$COUNT" -eq 7 ] || fail "--config-project: $COUNT/7 agents"
python3 -c "
import json
cfg = json.load(open('$PROJ2/opencode.json'))
assert 'agent' in cfg, 'missing agent key'
assert 'agents' not in cfg, 'has deprecated agents key'
assert '\$schema' in cfg, 'missing schema'
print('config OK')
" && pass || fail "--config-project config validation"

# ------------------------------------------------------------------
echo "=== 9. Config preserves unrelated keys ==="
export OPENCODE_CONFIG_DIR="$TEST_ROOT/preserve"
mkdir -p "$OPENCODE_CONFIG_DIR"
cat > "$OPENCODE_CONFIG_DIR/opencode.json" <<'JSON'
{
  "$schema": "https://opencode.ai/config.json",
  "agent": {
    "custom": {"description": "my agent", "mode": "all"}
  }
}
JSON
run_checked "preserve" bash agent.sh --config-global
python3 -c "
import json
cfg = json.load(open('$OPENCODE_CONFIG_DIR/opencode.json'))
assert 'custom' in cfg['agent'], 'custom agent lost'
assert cfg['agent']['custom']['description'] == 'my agent', 'custom agent modified'
print('preserved')
" && pass || fail "custom agent not preserved"

# ------------------------------------------------------------------
echo "=== 10. Repeated install produces no unnecessary backup ==="
export OPENCODE_CONFIG_DIR="$TEST_ROOT/idempotent"
mkdir -p "$OPENCODE_CONFIG_DIR"
run_checked "ido1" bash agent.sh --global
BEFORE=$(find "$OPENCODE_CONFIG_DIR" -name '*.bak.*' | wc -l)
run_checked "ido2" bash agent.sh --global
AFTER=$(find "$OPENCODE_CONFIG_DIR" -name '*.bak.*' | wc -l)
[ "$AFTER" -eq "$BEFORE" ] && pass || fail "repeat install created extra backups: $((AFTER - BEFORE))"

# ------------------------------------------------------------------
echo "=== 11. Changed files create backup ==="
export OPENCODE_CONFIG_DIR="$TEST_ROOT/backup_test"
mkdir -p "$OPENCODE_CONFIG_DIR"
run_checked "bt1" bash agent.sh --global
echo "# changed" >> "$OPENCODE_CONFIG_DIR/agents/heidi.md"
run_checked "bt2" bash agent.sh --global
BACKUP_COUNT=$(find "$OPENCODE_CONFIG_DIR/agents" -name 'heidi.md.bak.*' | wc -l)
[ "$BACKUP_COUNT" -ge 1 ] && pass || fail "changed file no backup"

# ------------------------------------------------------------------
echo "=== 12. --dry-run makes no changes ==="
export OPENCODE_CONFIG_DIR="$TEST_ROOT/dryrun"
mkdir -p "$OPENCODE_CONFIG_DIR"
run_checked "dryrun" bash agent.sh --dry-run --global
[ -d "$OPENCODE_CONFIG_DIR/agents" ] && fail "dry-run created agents dir" || pass

# ------------------------------------------------------------------
echo "=== 13. Uninstall removes only managed entries ==="
export OPENCODE_CONFIG_DIR="$TEST_ROOT/uninstall"
mkdir -p "$OPENCODE_CONFIG_DIR"
run_checked "uni1" bash agent.sh --global
mkdir -p "$OPENCODE_CONFIG_DIR/agents"
echo "custom" > "$OPENCODE_CONFIG_DIR/agents/custom.md"
run_checked "uni2" bash agent.sh --uninstall
HEIDI_GONE=true
[ ! -f "$OPENCODE_CONFIG_DIR/agents/heidi.md" ] || HEIDI_GONE=false
CUSTOM_OK=true
[ -f "$OPENCODE_CONFIG_DIR/agents/custom.md" ] || CUSTOM_OK=false
[ "$HEIDI_GONE" = true ] && [ "$CUSTOM_OK" = true ] && pass || fail "uninstall: heidi_gone=$HEIDI_GONE custom=$CUSTOM_OK"

# ------------------------------------------------------------------
echo "=== 14. --init-rules creates all three .heidi files ==="
HEIDI_DIR="$TEST_ROOT/heidi_init"
mkdir -p "$HEIDI_DIR"
run_checked "init" bash -c "cd '$HEIDI_DIR' && bash '$REPO_ROOT/agent.sh' --init-rules"
ALL_OK=true
[ -f "$HEIDI_DIR/.heidi/rules.md" ] || { ALL_OK=false; echo "  missing rules.md"; }
[ -f "$HEIDI_DIR/.heidi/commands.md" ] || { ALL_OK=false; echo "  missing commands.md"; }
[ -f "$HEIDI_DIR/.heidi/memory.jsonl" ] || { ALL_OK=false; echo "  missing memory.jsonl"; }
[ "$ALL_OK" = true ] && pass || fail "--init-rules incomplete"

# ------------------------------------------------------------------
echo "=== 15. Repeated --init-rules preserves existing ==="
run_checked "init2" bash -c "cd '$HEIDI_DIR' && bash '$REPO_ROOT/agent.sh' --init-rules"
[ -f "$HEIDI_DIR/.heidi/rules.md" ] && pass || fail "second --init-rules removed files"

# ------------------------------------------------------------------
echo "=== 16. --repair produces valid complete installation ==="
export OPENCODE_CONFIG_DIR="$TEST_ROOT/repair"
mkdir -p "$OPENCODE_CONFIG_DIR"
run_checked "repair" bash agent.sh --repair
COUNT=0
for a in heidi frontend backend debugger auditor planner scout; do
  [ -f "$OPENCODE_CONFIG_DIR/agents/$a.md" ] && COUNT=$((COUNT + 1))
done
CONFIG_OK=false
[ -f "$(pwd)/opencode.json" ] && CONFIG_OK=true
rm -f "$(pwd)/opencode.json"
[ "$COUNT" -eq 7 ] && [ "$CONFIG_OK" = true ] && pass || fail "--repair incomplete"

# ------------------------------------------------------------------
echo "=== 17. --check reports expected paths ==="
run_checked "check" bash agent.sh --check
grep -q "Source agents:" "$OUTDIR/check.stdout" && pass || fail "--check output"

# ------------------------------------------------------------------
echo "=== 18. --doctor works ==="
run_checked "doctor" bash agent.sh --doctor
[ -s "$OUTDIR/doctor.stdout" ] && pass || fail "--doctor failed"

# ------------------------------------------------------------------
echo "=== 19. Invalid JSON config doesn't destroy file ==="
export OPENCODE_CONFIG_DIR="$TEST_ROOT/badjson"
mkdir -p "$OPENCODE_CONFIG_DIR"
echo "{{{not json}}" > "$OPENCODE_CONFIG_DIR/opencode.json"
run_checked "badjson" bash agent.sh --config-global
[ -f "$OPENCODE_CONFIG_DIR/opencode.json" ] && pass || fail "original file destroyed on bad JSON"

# ------------------------------------------------------------------
echo "=== 20. Config uses 'agent' not 'agents' ==="
export OPENCODE_CONFIG_DIR="$TEST_ROOT/keycheck"
mkdir -p "$OPENCODE_CONFIG_DIR"
run_checked "keycheck" bash agent.sh --config-global
python3 -c "
import json
cfg = json.load(open('$OPENCODE_CONFIG_DIR/opencode.json'))
assert 'agent' in cfg, 'no agent key'
assert 'agents' not in cfg, 'deprecated agents key'
print('OK')
" && pass || fail "config uses wrong key"

summary
