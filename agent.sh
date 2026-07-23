#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_SRC="$SCRIPT_DIR/opencode-agent-pack/agents"
VERSION_FILE="$SCRIPT_DIR/opencode-agent-pack/VERSION"
PACK_VERSION="$(cat "$VERSION_FILE" 2>/dev/null || echo 'unknown')"

# One canonical managed-agent list shared throughout the script.
AGENT_NAMES=(heidi frontend backend debugger auditor planner scout)

usage() {
  local exit_code="${1:-0}"
  cat <<EOF
Usage: $0 [options]

Install OpenCode Heidi agent pack v$PACK_VERSION.

Options:
  --global              Install into OPENCODE_CONFIG_DIR or ~/.config/opencode/agents (default)
  --project             Install into .opencode/agents in the current directory
  --both                Install into both global and project official paths
  --check               Print diagnostic information without installing
  --doctor              Print runtime discovery diagnostics
  --dry-run             Show what would be installed without doing it
  --diff                Show diff between installed and source agents
  --config-global       Update global opencode.json with agent definitions
  --config-project      Update project opencode.json with agent definitions
  --default AGENT       Set default_agent in opencode.json
  --init-rules          Create .heidi/rules.md, commands.md, and memory.jsonl
  --force               With --init-rules, reinitialize existing files (with backup)
  --repair              Run all install paths + config + doctor
  --uninstall           Remove Heidi pack agents and config entries
  --rollback            Restore newest backup set
  --version             Show pack version and exit

If no flag is given, --global is assumed.
EOF
  exit "$exit_code"
}

if [ ! -d "$AGENT_SRC" ]; then
  echo "Error: agent source directory not found at $AGENT_SRC"
  echo "Run this script from the repo root."
  exit 1
fi

# --- Handle --version early ---
for arg in "$@"; do
  if [ "$arg" = "--version" ]; then
    echo "Heidi OpenCode Agent Pack version $PACK_VERSION"
    exit 0
  fi
done

CONFIG_DIR="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"

# --- Flags ---
MODE="global"
DO_CONFIG_GLOBAL=false
DO_CONFIG_PROJECT=false
DO_DEFAULT=false
DEFAULT_AGENT=""
DRY_RUN=false
DO_UNINSTALL=false
DO_ROLLBACK=false
DO_INIT_RULES=false
DO_FORCE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --global) MODE="global"; shift ;;
    --project) MODE="project"; shift ;;
    --both) MODE="both"; shift ;;
    --check) MODE="check"; shift ;;
    --doctor) MODE="doctor"; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    --diff) MODE="diff"; shift ;;
    --config-global) DO_CONFIG_GLOBAL=true; shift ;;
    --config-project) DO_CONFIG_PROJECT=true; shift ;;
    --init-rules) DO_INIT_RULES=true; shift ;;
    --force) DO_FORCE=true; shift ;;
    --repair) MODE="repair"; shift ;;
    --uninstall) DO_UNINSTALL=true; shift ;;
    --rollback) DO_ROLLBACK=true; shift ;;
    --default)
      DO_DEFAULT=true
      shift
      if [ $# -eq 0 ]; then echo "Error: --default requires an agent name" >&2; usage 2; fi
      DEFAULT_AGENT="$1"
      shift
      ;;
    -h|--help) usage 0 ;;
    *)
      echo "Error: unknown option: $1" >&2
      usage 2
      ;;
  esac
done

# Validate --default agent name
if [ "$DO_DEFAULT" = true ]; then
  valid=false
  for a in "${AGENT_NAMES[@]}"; do
    if [ "$a" = "$DEFAULT_AGENT" ]; then valid=true; break; fi
  done
  if [ "$valid" = false ]; then
    echo "Error: unknown agent '$DEFAULT_AGENT'. Valid: ${AGENT_NAMES[*]}" >&2
    exit 1
  fi
  if [ "$DO_CONFIG_GLOBAL" = false ] && [ "$DO_CONFIG_PROJECT" = false ]; then
    echo "Error: --default requires --config-global or --config-project" >&2
    exit 1
  fi
fi

# ============================================================
# INSTALL FUNCTION
# ============================================================
install_to() {
  local target="$1"
  local label="$2"
  if [ "$DRY_RUN" = true ]; then
    echo "[dry-run] Would install agents to $target ($label)"
    for agent in "${AGENT_NAMES[@]}"; do
      src="$AGENT_SRC/$agent.md"
      dst="$target/$agent.md"
      if [ ! -f "$src" ]; then
        echo "[dry-run]   Warning: source $src not found, skipping $agent"
        continue
      fi
      if [ -f "$dst" ] && cmp -s "$src" "$dst"; then
        echo "[dry-run]   $agent: unchanged, would skip"
      elif [ -f "$dst" ]; then
        echo "[dry-run]   $agent: would back up $dst and copy"
      else
        echo "[dry-run]   $agent: would install to $dst"
      fi
    done
    return
  fi
  mkdir -p "$target"
  TIMESTAMP=$(date +%Y%m%d-%H%M%S)
  for agent in "${AGENT_NAMES[@]}"; do
    src="$AGENT_SRC/$agent.md"
    dst="$target/$agent.md"
    if [ ! -f "$src" ]; then
      echo "Warning: source file $src not found, skipping $agent"
      continue
    fi
    if [ -f "$dst" ] && cmp -s "$src" "$dst"; then
      echo "Unchanged: $dst"
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
  echo "Installed agents ($label):"
  for agent in "${AGENT_NAMES[@]}"; do
    dst="$target/$agent.md"
    if [ -f "$dst" ]; then
      echo "  $dst"
    fi
  done
}

# ============================================================
# CHECK MODE
# ============================================================
check_mode() {
  echo "=== OpenCode Agent Pack Diagnostics ==="
  echo "Pack version: $PACK_VERSION"
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
}

# ============================================================
# DOCTOR MODE
# ============================================================
doctor_mode() {
  echo "=== OpenCode Agent Discovery Doctor ==="
  echo "Pack version: $PACK_VERSION"
  echo "opencode binary path: $(command -v opencode 2>/dev/null || echo 'NOT FOUND')"
  if command -v opencode >/dev/null 2>&1; then
    echo "opencode version: $(opencode --version 2>/dev/null || opencode version 2>/dev/null || echo 'unknown')"
  else
    echo "opencode version: N/A (not installed)"
  fi
  echo "current user: $(whoami)"
  echo "HOME=$HOME"
  echo "PWD=$(pwd)"
  echo "OPENCODE_CONFIG=${OPENCODE_CONFIG:-}"
  echo "OPENCODE_CONFIG_DIR=${OPENCODE_CONFIG_DIR:-}"
  echo "global markdown agent directory: $CONFIG_DIR/agents"
  echo "project markdown agent directory: $(pwd)/.opencode/agents"
  echo "global opencode.json path: $CONFIG_DIR/opencode.json"
  echo "project opencode.json path: $(pwd)/opencode.json"
  echo ""
  echo "--- File checks ---"
  for d in "$CONFIG_DIR/agents" "$(pwd)/.opencode/agents"; do
    if [ -d "$d" ]; then
      echo "  $d: EXISTS ($(find "$d" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l) .md files)"
    else
      echo "  $d: NOT FOUND"
    fi
  done
  for j in "$CONFIG_DIR/opencode.json" "$(pwd)/opencode.json"; do
    if [ -f "$j" ]; then
      echo "  $j: EXISTS ($(wc -c < "$j") bytes)"
    else
      echo "  $j: NOT FOUND"
    fi
  done
  echo ""
  echo "--- opencode agent list ---"
  if command -v opencode >/dev/null 2>&1; then
    if AGENT_LIST=$(opencode agent list 2>/dev/null); then
      echo "$AGENT_LIST"
    else
      echo "(opencode agent list returned non-zero exit)"
      opencode agent list 2>&1 || true
    fi
    echo ""
    echo "--- Agent presence in opencode agent list ---"
    for agent in "${AGENT_NAMES[@]}"; do
      if echo "$AGENT_LIST" | grep -qi "$agent"; then
        echo "  $agent: FOUND"
      else
        echo "  $agent: NOT FOUND"
      fi
    done
  else
    echo "(opencode not available on this machine)"
  fi
}

# ============================================================
# JSON CONFIG FUNCTIONS
# ============================================================
generate_agent_json() {
  local prompt_prefix="$1"
  export OC_PREFIX="$prompt_prefix"
  python3 <<'PYEOF' || { echo "Error: JSON generation failed" >&2; exit 1; }
import json, os, sys, tempfile

prompt_prefix = os.environ["OC_PREFIX"]
config_path = os.environ["OC_CONFIG_PATH"]
default_agent = os.environ.get("OC_DEFAULT_AGENT", "")

# Build the agent configurations matching Markdown frontmatter exactly.
# Heidi: primary with task allowlist
# Specialists: subagent with task: deny
# Read-only: auditor, planner, scout get bash: deny + edit: deny
# Writable: frontend, backend, debugger get edit: allow, bash: allow
agent_configs = {
    "heidi": {
        "description": "Primary orchestrator agent that coordinates all custom agents and handles general-purpose development",
        "mode": "primary",
        "temperature": 0.2,
        "prompt": "{file:%s/heidi.md}" % prompt_prefix,
        "permission": {
            "edit": "allow",
            "bash": "allow",
            "task": {
                "*": "deny",
                "scout": "allow",
                "frontend": "allow",
                "backend": "allow",
                "debugger": "allow",
                "auditor": "allow",
                "planner": "allow"
            }
        }
    },
    "scout": {
        "description": "Project reconnaissance and stack detection specialist",
        "mode": "subagent",
        "temperature": 0.1,
        "prompt": "{file:%s/scout.md}" % prompt_prefix,
        "permission": {
            "edit": "deny",
            "bash": "deny",
            "task": "deny"
        }
    },
    "planner": {
        "description": "Feature planning and specification specialist for requirements, architecture, and task breakdown",
        "mode": "subagent",
        "temperature": 0.1,
        "prompt": "{file:%s/planner.md}" % prompt_prefix,
        "permission": {
            "edit": "deny",
            "bash": "deny",
            "task": "deny"
        }
    },
    "auditor": {
        "description": "Read-only code review and architecture analysis specialist",
        "mode": "subagent",
        "temperature": 0.1,
        "prompt": "{file:%s/auditor.md}" % prompt_prefix,
        "permission": {
            "edit": "deny",
            "bash": "deny",
            "task": "deny"
        }
    },
    "frontend": {
        "description": "Frontend/UI specialist for React, TypeScript, Tailwind, Next.js, Vite, UX polish, and component architecture",
        "mode": "subagent",
        "temperature": 0.2,
        "prompt": "{file:%s/frontend.md}" % prompt_prefix,
        "permission": {"edit": "allow", "bash": "allow", "task": "deny"}
    },
    "backend": {
        "description": "Backend/API/database specialist for server logic, Prisma, auth, migrations, and deployment-safe changes",
        "mode": "subagent",
        "temperature": 0.1,
        "prompt": "{file:%s/backend.md}" % prompt_prefix,
        "permission": {"edit": "allow", "bash": "allow", "task": "deny"}
    },
    "debugger": {
        "description": "Debugging and root-cause analysis specialist for bugs, CI failures, regressions, and broken builds",
        "mode": "subagent",
        "temperature": 0.1,
        "prompt": "{file:%s/debugger.md}" % prompt_prefix,
        "permission": {"edit": "allow", "bash": "allow", "task": "deny"}
    }
}

# Read existing config
existing = {}
if os.path.exists(config_path):
    with open(config_path, encoding="utf-8") as f:
        existing = json.load(f)

# Preserve $schema
if "$schema" not in existing:
    existing["$schema"] = "https://opencode.ai/config.json"

# Ensure "agent" key (singular) - do NOT use deprecated "agents"
if "agent" not in existing:
    existing["agent"] = {}

# Update only the seven managed agents; preserve others
existing["agent"].update(agent_configs)

# Remove any deprecated "agents" key
existing.pop("agents", None)

if default_agent:
    existing["default_agent"] = default_agent

# Atomic write: write to temp file then mv
tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(config_path) or ".", suffix=".tmp")
try:
    with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)
        f.write("\n")
    os.replace(tmp_path, config_path)
except Exception as exc:
    os.unlink(tmp_path)
    raise SystemExit(f"atomic write failed: {exc}")

print("Updated %s" % config_path)
PYEOF
}

write_json_config() {
  local config_file="$1"
  local prompt_prefix="$2"
  local default_agent_arg="${3:-}"

  if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required for JSON config management. Install python3 and try again." >&2
    echo "No changes were made to $config_file."
    return 1
  fi

  if [ "$DRY_RUN" = true ]; then
    echo "[dry-run] Would update $config_file with agent definitions"
    if [ -n "$default_agent_arg" ]; then
      echo "[dry-run] Would set default_agent=$default_agent_arg"
    fi
    return 0
  fi

  # Compare generated config with existing before backing up
  export OC_CONFIG_PATH="$config_file"
  export OC_DEFAULT_AGENT="$default_agent_arg"
  # Write to a temp comparison target first to check if backup is needed
  local tmp_config
  tmp_config="$(mktemp)"
  if OC_CONFIG_PATH="$tmp_config" OC_DEFAULT_AGENT="$default_agent_arg" \
       bash -c 'source /dev/stdin' <<<"$(declare -f generate_agent_json); generate_agent_json \"$1\"" _ "$prompt_prefix" 2>/dev/null; then
    if [ -f "$config_file" ] && cmp -s "$config_file" "$tmp_config"; then
      echo "Unchanged: $config_file"
      rm -f "$tmp_config"
      return 0
    fi
  fi
  rm -f "$tmp_config"

  if [ -f "$config_file" ]; then
    local backup
    backup="$config_file.bak.$(date +%Y%m%d-%H%M%S)"
    cp "$config_file" "$backup"
    echo "Backed up existing $config_file -> $backup"
  fi

  export OC_CONFIG_PATH="$config_file"
  export OC_DEFAULT_AGENT="$default_agent_arg"
  generate_agent_json "$prompt_prefix"
  validate_generated_config "$config_file"
}

validate_generated_config() {
  local config_file="$1"
  if [ ! -f "$config_file" ]; then
    echo "Config file not found: $config_file" >&2
    return 1
  fi
  python3 - "$config_file" <<'PY' || return 1
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
config_dir = path.parent

with path.open(encoding="utf-8") as handle:
    config = json.load(handle)

if "agents" in config:
    raise SystemExit("invalid deprecated key: agents")

agents = config.get("agent")
if not isinstance(agents, dict):
    raise SystemExit("missing or invalid agent object")

required = {"heidi", "frontend", "backend", "debugger", "auditor", "planner", "scout"}
missing = sorted(required.difference(agents))
if missing:
    raise SystemExit(f"missing agents: {', '.join(missing)}")

# Verify prompt paths exist (resolve relative to config file directory)
for name in required:
    prompt = agents[name].get("prompt", "")
    if not prompt:
        raise SystemExit(f"{name}: missing prompt")
    if prompt.startswith("{file:"):
        ref = prompt[len("{file:"):-1]
        ref_path = config_dir / ref
        if not ref_path.exists():
            raise SystemExit(f"{name}: prompt file not found: {ref_path}")

print(f"Config validation PASSED: {path}")
PY
}

# ============================================================
# UNINSTALL FUNCTION
# ============================================================
uninstall_from() {
  local target="$1"
  local label="$2"
  local config_file="${3:-}"
  if [ "$DRY_RUN" = true ]; then
    echo "[dry-run] Would uninstall from $label ($target)"
    for agent in "${AGENT_NAMES[@]}"; do
      file="$target/$agent.md"
      if [ -f "$file" ]; then
        echo "[dry-run]   Would remove $file"
      fi
    done
    if [ -n "$config_file" ] && [ -f "$config_file" ]; then
      echo "[dry-run]   Would remove Heidi entries from $config_file"
    fi
    return
  fi
  if [ ! -d "$target" ]; then
    echo "  (directory does not exist, skipping)"
    return
  fi
  for agent in "${AGENT_NAMES[@]}"; do
    file="$target/$agent.md"
    if [ -f "$file" ]; then
      rm "$file"
      echo "Removed: $file"
    fi
  done
  # Remove Heidi entries from JSON config
  if [ -n "$config_file" ] && [ -f "$config_file" ]; then
    python3 - "$config_file" <<'PY' || true
import json
import sys
path = sys.argv[1]
with open(path) as f:
    config = json.load(f)
heidi_agents = {"heidi","frontend","backend","debugger","auditor","planner","scout"}
if "agent" in config:
    for name in heidi_agents:
        config["agent"].pop(name, None)
with open(path, 'w') as f:
    json.dump(config, f, indent=2)
    f.write("\n")
print(f"Removed Heidi entries from {path}")
PY
  fi
  rmdir "$target" 2>/dev/null || true
}

# ============================================================
# ROLLBACK FUNCTION
# ============================================================
rollback_from() {
  local target_dir="$1"
  local label="$2"
  local config_file="${3:-}"
  if [ ! -d "$target_dir" ]; then
    echo "  $label: no target directory, skipping"
    return
  fi
  local restored=false
  for agent in "${AGENT_NAMES[@]}"; do
    file="$target_dir/$agent.md"
    if [ -f "$file" ]; then
      # Find newest backup
      local backup
      backup="$(find "$(dirname "$file")" -maxdepth 1 -name "$(basename "$file").bak.*" -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)" || true
      if [ -n "$backup" ] && [ -f "$backup" ]; then
        cp "$backup" "$file"
        echo "Restored: $file <- $backup"
        restored=true
      fi
    fi
  done
  # Rollback JSON config if backup exists
  if [ -n "$config_file" ] && [ -f "$config_file" ]; then
    local cfg_backup
    cfg_backup="$(find "$(dirname "$config_file")" -maxdepth 1 -name "$(basename "$config_file").bak.*" -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)" || true
    if [ -n "$cfg_backup" ] && [ -f "$cfg_backup" ]; then
      cp "$cfg_backup" "$config_file"
      echo "Restored: $config_file <- $cfg_backup"
      restored=true
    fi
  fi
  if [ "$restored" = false ]; then
    echo "  $label: no backups found"
  fi
}

# ============================================================
# INIT RULES
# ============================================================
init_rules_mode() {
  local target_dir
  target_dir="$(pwd)/.heidi"
  mkdir -p "$target_dir"

  # rules.md (stack-neutral template)
  local rules_file="$target_dir/rules.md"
  if [ -f "$rules_file" ] && [ "$DO_FORCE" = false ]; then
    echo "Skipped (exists): $rules_file"
  else
    if [ -f "$rules_file" ]; then
      cp "$rules_file" "$rules_file.bak.$(date +%Y%m%d-%H%M%S)"
      echo "Backed up: $rules_file"
    fi
    cat > "$rules_file" <<RULESEOF
# Repository Rules

This file contains reviewed and durable repository policies for Heidi AI agents.

## Architecture Boundaries
-

## Coding Conventions
-

## Forbidden Patterns
-

## Package-Management Rules
-

## Deployment Constraints
-

## Human-Operation Rules
-

RULESEOF
    echo "Created: $rules_file"
  fi

  # commands.md
  local commands_file="$target_dir/commands.md"
  if [ -f "$commands_file" ] && [ "$DO_FORCE" = false ]; then
    echo "Skipped (exists): $commands_file"
  else
    if [ -f "$commands_file" ]; then
      cp "$commands_file" "$commands_file.bak.$(date +%Y%m%d-%H%M%S)"
      echo "Backed up: $commands_file"
    fi
    cat > "$commands_file" <<CMDSHEOF
# Verified Repository Commands

- Install:
- Format:
- Lint:
- Typecheck:
- Unit tests:
- Integration tests:
- End-to-end tests:
- Build:
- Production smoke:
CMDSHEOF
    echo "Created: $commands_file"
  fi

  # memory.jsonl
  local   memory_file="$target_dir/memory.jsonl"
  if [ -f "$memory_file" ] && [ "$DO_FORCE" = false ]; then
    echo "Skipped (exists): $memory_file"
  else
    if [ -f "$memory_file" ]; then
      cp "$memory_file" "$memory_file.bak.$(date +%Y%m%d-%H%M%S)"
      echo "Backed up: $memory_file"
    fi
    : > "$memory_file"
    echo "Created: $memory_file"
  fi
}

# ============================================================
# DRY-RUN MODE
# ============================================================
dry_run_mode() {
  echo "=== Dry Run: What Would Be Installed ==="
  echo ""
  echo "Source agents:"
  for agent in "${AGENT_NAMES[@]}"; do
    src="$AGENT_SRC/$agent.md"
    if [ -f "$src" ]; then
      echo "  $agent.md ($(wc -c < "$src" | tr -d ' ') bytes)"
    else
      echo "  $agent.md (NOT FOUND)"
    fi
  done
  echo ""
  echo "Would install to:"
  echo "  Global: $OFFICIAL_GLOBAL"
  echo "  Project: $OFFICIAL_PROJECT"
  echo ""
  echo "Existing files that would be backed up:"
  local found=false
  for target_dir in "$OFFICIAL_GLOBAL" "$OFFICIAL_PROJECT"; do
    for agent in "${AGENT_NAMES[@]}"; do
      dst="$target_dir/$agent.md"
      if [ -f "$dst" ]; then
        echo "  $dst"
        found=true
      fi
    done
  done
  if [ "$found" = false ]; then
    echo "  (none)"
  fi
  echo ""
  echo "No changes were made. Run without --dry-run to install."
}

# ============================================================
# DIFF MODE
# ============================================================
diff_mode() {
  echo "=== Diff: Source vs Installed ==="
  local any_diff=false
  for target_dir in "$OFFICIAL_GLOBAL" "$OFFICIAL_PROJECT"; do
    if [ ! -d "$target_dir" ]; then
      continue
    fi
    for agent in "${AGENT_NAMES[@]}"; do
      src="$AGENT_SRC/$agent.md"
      dst="$target_dir/$agent.md"
      if [ ! -f "$src" ]; then
        continue
      fi
      if [ ! -f "$dst" ]; then
        echo "--- $agent.md: NOT INSTALLED at $target_dir"
        any_diff=true
        continue
      fi
      if ! diff -q "$src" "$dst" > /dev/null 2>&1; then
        echo ""
        echo "=== $agent.md ($target_dir) ==="
        diff -u "$dst" "$src" || true
        any_diff=true
      fi
    done
  done
  if [ "$any_diff" = false ]; then
    echo "All installed agents match source. No differences found."
  fi
}

# ============================================================
# MAIN LOGIC
# ============================================================

OFFICIAL_GLOBAL="$CONFIG_DIR/agents"
OFFICIAL_PROJECT="$(pwd)/.opencode/agents"

# ---- Non-install modes ----
case "${MODE:-global}" in
  check) check_mode; exit 0 ;;
  doctor) doctor_mode; exit 0 ;;
  diff) diff_mode; exit 0 ;;
esac

# --init-rules mode
if [ "$DO_INIT_RULES" = true ]; then
  init_rules_mode
  exit 0
fi

# --uninstall mode
if [ "$DO_UNINSTALL" = true ]; then
  echo "=== Uninstall Heidi Agent Pack ==="
  echo ""
  uninstall_from "$OFFICIAL_GLOBAL" "global official" "$CONFIG_DIR/opencode.json"
  uninstall_from "$OFFICIAL_PROJECT" "project official" "$(pwd)/opencode.json"
  if [ "$DRY_RUN" = false ]; then
    echo "Done. Only Heidi pack agents were removed."
  fi
  exit 0
fi

# --rollback mode
if [ "$DO_ROLLBACK" = true ]; then
  echo "=== Rollback Heidi Agent Pack ==="
  echo ""
  rollback_from "$OFFICIAL_GLOBAL" "global official" "$CONFIG_DIR/opencode.json"
  rollback_from "$OFFICIAL_PROJECT" "project official" "$(pwd)/opencode.json"
  echo "Done."
  exit 0
fi

# --- Dry-run mode ---
if [ "$DRY_RUN" = true ] && [ "$MODE" != "repair" ]; then
  dry_run_mode
  exit 0
fi

# --- Install ---
do_install() {
  local targets=()
  local labels=()

  if [ "$MODE" = "global" ] || [ "$MODE" = "both" ]; then
    targets+=("$OFFICIAL_GLOBAL")
    labels+=("global official")
  fi
  if [ "$MODE" = "project" ] || [ "$MODE" = "both" ]; then
    targets+=("$OFFICIAL_PROJECT")
    labels+=("project official")
  fi

  for i in "${!targets[@]}"; do
    install_to "${targets[$i]}" "${labels[$i]}"
    echo ""
  done
}

# --- Repair mode ---
if [ "$MODE" = "repair" ]; then
  echo "=== OpenCode Agent Pack Repair ==="
  echo ""
  if [ "$DRY_RUN" = true ]; then
    echo "[dry-run] Repair mode:"
    echo "[dry-run]   Would install agents to all paths"
    echo "[dry-run]   Would write project JSON config"
    echo "[dry-run]   Would run diagnostics"
    echo ""
    MODE="both"
    do_install
    echo "[dry-run]   Write project JSON config"
    exit 0
  fi
  MODE="both"
  do_install
  echo "=== Project JSON config ==="
  write_json_config "$(pwd)/opencode.json" ".opencode/agents" "${DEFAULT_AGENT:-}"
  echo ""
  echo "=== Doctor diagnostics ==="
  doctor_mode
  exit 0
fi

do_install

# --- JSON config (with implied agent install) ---
if [ "$DO_CONFIG_GLOBAL" = true ]; then
  # Ensure global agent files are installed for the config reference
  mkdir -p "$OFFICIAL_GLOBAL"
  for agent in "${AGENT_NAMES[@]}"; do
    src="$AGENT_SRC/$agent.md"
    dst="$OFFICIAL_GLOBAL/$agent.md"
    if [ -f "$src" ] && { [ ! -f "$dst" ] || ! cmp -s "$src" "$dst"; }; then
      cp "$src" "$dst"
    fi
  done
  echo ""
  echo "=== Global JSON config ==="
  write_json_config "$CONFIG_DIR/opencode.json" "./agents" "${DEFAULT_AGENT:-}"
fi

if [ "$DO_CONFIG_PROJECT" = true ]; then
  # Ensure project agent files are installed for the config reference
  mkdir -p "$OFFICIAL_PROJECT"
  for agent in "${AGENT_NAMES[@]}"; do
    src="$AGENT_SRC/$agent.md"
    dst="$OFFICIAL_PROJECT/$agent.md"
    if [ -f "$src" ] && { [ ! -f "$dst" ] || ! cmp -s "$src" "$dst"; }; then
      cp "$src" "$dst"
    fi
  done
  echo ""
  echo "=== Project JSON config ==="
  write_json_config "$(pwd)/opencode.json" ".opencode/agents" "${DEFAULT_AGENT:-}"
fi

echo ""
echo "Done. Heidi OpenCode Agent Pack v$PACK_VERSION installed."
echo "Official OpenCode build and plan agents were not modified."
echo ""
echo "Need troubleshooting? Run: ./agent.sh --doctor"
