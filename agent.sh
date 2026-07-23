#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_SRC="$SCRIPT_DIR/opencode-agent-pack/agents"
AGENT_NAMES=(heidi frontend backend debugger auditor planner scout)

usage() {
  cat <<EOF
Usage: $0 [options]

Install OpenCode Heidi agent pack.

Options:
  --global              Install into OPENCODE_CONFIG_DIR or ~/.config/opencode/agents (default)
  --project             Install into .opencode/agents in the current directory
  --both                Install into both global and project official paths
  --legacy              Also install into legacy paths (agent/ singular, not agents/)
                        Combine with --global, --project, or --both
  --check               Print diagnostic information without installing
  --doctor              Print runtime discovery diagnostics
  --dry-run             Show what would be installed without doing it
  --diff                Show diff between installed and source agents
  --config-global       Update global opencode.json with agent definitions
  --config-project      Update project opencode.json with agent definitions
  --default AGENT       Set default_agent in opencode.json (requires --config-global or --config-project)
  --repair              Run all install paths + config + doctor

If no flag is given, --global is assumed.
EOF
  exit 0
}

if [ ! -d "$AGENT_SRC" ]; then
  echo "Error: agent source directory not found at $AGENT_SRC"
  echo "Run this script from the repo root."
  exit 1
fi

CONFIG_DIR="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"

# --- Determine mode flags ---
MODE="global"
DO_LEGACY=false
DO_CONFIG_GLOBAL=false
DO_CONFIG_PROJECT=false
DO_DEFAULT=false
DEFAULT_AGENT=""
POSITIONAL=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --global) MODE="global"; shift ;;
    --project) MODE="project"; shift ;;
    --both) MODE="both"; shift ;;
    --legacy) DO_LEGACY=true; shift ;;
    --check) MODE="check"; shift ;;
    --doctor) MODE="doctor"; shift ;;
    --dry-run) MODE="dry-run"; shift ;;
    --diff) MODE="diff"; shift ;;
    --config-global) DO_CONFIG_GLOBAL=true; shift ;;
    --config-project) DO_CONFIG_PROJECT=true; shift ;;
    --repair) MODE="repair"; shift ;;
    --default)
      DO_DEFAULT=true
      shift
      if [ $# -eq 0 ]; then echo "Error: --default requires an agent name"; exit 1; fi
      DEFAULT_AGENT="$1"
      shift
      ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

# Validate --default agent name
if [ "$DO_DEFAULT" = true ]; then
  valid=false
  for a in "${AGENT_NAMES[@]}"; do
    if [ "$a" = "$DEFAULT_AGENT" ]; then valid=true; break; fi
  done
  if [ "$valid" = false ]; then
    echo "Error: unknown agent '$DEFAULT_AGENT'. Valid: ${AGENT_NAMES[*]}"
    exit 1
  fi
  if [ "$DO_CONFIG_GLOBAL" = false ] && [ "$DO_CONFIG_PROJECT" = false ]; then
    echo "Error: --default requires --config-global or --config-project"
    exit 1
  fi
fi

# If only --default flags, skip install
if [ "$DO_DEFAULT" = true ] && [ "$DO_CONFIG_GLOBAL" = false ] && [ "$DO_CONFIG_PROJECT" = false ]; then
  echo "Error: --default requires --config-global or --config-project"
  exit 1
fi

# ============================================================
# INSTALL FUNCTION
# ============================================================
install_to() {
  local target="$1"
  local label="$2"
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
  echo "legacy singular global agent directory: $CONFIG_DIR/agent"
  echo "legacy singular project agent directory: $(pwd)/.opencode/agent"
  echo "global opencode.json path: $CONFIG_DIR/opencode.json"
  echo "project opencode.json path: $(pwd)/opencode.json"
  echo ""
  echo "--- File checks ---"
  for d in "$CONFIG_DIR/agents" "$CONFIG_DIR/agent" "$(pwd)/.opencode/agents" "$(pwd)/.opencode/agent"; do
    if [ -d "$d" ]; then
      echo "  $d: EXISTS ($(ls "$d"/*.md 2>/dev/null | wc -l) .md files)"
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
  python3 <<'PYEOF'
import json, os

prompt_prefix = os.environ["OC_PREFIX"]
config_path = os.environ["OC_CONFIG_PATH"]
default_agent = os.environ.get("OC_DEFAULT_AGENT", "")

agent_configs = {
    "heidi": {
        "description": "Primary orchestrator agent that coordinates all custom agents and handles general-purpose development",
        "mode": "all",
        "temperature": 0.2,
        "prompt": "{file:%s/heidi.md}" % prompt_prefix,
        "permission": {"edit": "allow", "bash": "allow", "task": "allow"}
    },
    "frontend": {
        "description": "Frontend/UI specialist for React, TypeScript, Tailwind, Next.js, Vite, UX polish, and component architecture",
        "mode": "all",
        "temperature": 0.2,
        "prompt": "{file:%s/frontend.md}" % prompt_prefix,
        "permission": {"edit": "allow", "bash": "allow"}
    },
    "backend": {
        "description": "Backend/API/database specialist for server logic, Prisma, auth, migrations, and deployment-safe changes",
        "mode": "all",
        "temperature": 0.1,
        "prompt": "{file:%s/backend.md}" % prompt_prefix,
        "permission": {"edit": "allow", "bash": "allow"}
    },
    "debugger": {
        "description": "Debugging and root-cause analysis specialist for bugs, CI failures, regressions, and broken builds",
        "mode": "all",
        "temperature": 0.1,
        "prompt": "{file:%s/debugger.md}" % prompt_prefix,
        "permission": {"edit": "allow", "bash": "allow"}
    },
    "auditor": {
        "description": "Read-only code review and architecture analysis specialist",
        "mode": "all",
        "temperature": 0.1,
        "prompt": "{file:%s/auditor.md}" % prompt_prefix,
        "permission": {
            "edit": "deny",
            "bash": {
                "*": "ask",
                "git status*": "allow",
                "git diff*": "allow",
                "git log*": "allow",
                "git show*": "allow",
                "ls*": "allow",
                "pwd": "allow",
                "cat*": "allow",
                "grep*": "allow",
                "find*": "allow"
            }
        }
    },
    "planner": {
        "description": "Feature planning and specification specialist for requirements, architecture, and task breakdown",
        "mode": "all",
        "temperature": 0.1,
        "prompt": "{file:%s/planner.md}" % prompt_prefix,
        "permission": {"edit": "deny", "bash": "deny"}
    },
    "scout": {
        "description": "Project reconnaissance and stack detection specialist",
        "mode": "all",
        "temperature": 0.1,
        "prompt": "{file:%s/scout.md}" % prompt_prefix,
        "permission": {
            "edit": "deny",
            "bash": {
                "*": "ask",
                "cat*": "allow",
                "ls*": "allow",
                "find*": "allow",
                "grep*": "allow",
                "head*": "allow",
                "tail*": "allow",
                "wc*": "allow",
                "file*": "allow",
                "pwd": "allow",
                "tree*": "allow"
            }
        }
    }
}

existing = {}
if os.path.exists(config_path):
    with open(config_path) as f:
        existing = json.load(f)

if "agents" not in existing:
    existing["agents"] = {}

existing["agents"].update(agent_configs)

if default_agent:
    existing["default_agent"] = default_agent

with open(config_path, "w") as f:
    json.dump(existing, f, indent=2)
    f.write("\n")

print("Updated %s" % config_path)
PYEOF
}

write_json_config() {
  local config_file="$1"
  local prompt_prefix="$2"
  local default_agent_arg="${3:-}"

  if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required for JSON config management. Install python3 and try again."
    echo "No changes were made to $config_file."
    return 1
  fi

  if [ -f "$config_file" ]; then
    local backup="$config_file.bak.$(date +%Y%m%d-%H%M%S)"
    cp "$config_file" "$backup"
    echo "Backed up existing $config_file -> $backup"
  fi

  export OC_CONFIG_PATH="$config_file"
  export OC_DEFAULT_AGENT="$default_agent_arg"
  generate_agent_json "$prompt_prefix"
}

# ============================================================
# MAIN LOGIC
# ============================================================

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
      echo "  $agent.md (NOT FOUND — would be skipped)"
    fi
  done
  echo ""
  echo "Would install to:"
  echo "  Global: $OFFICIAL_GLOBAL"
  echo "  Project: $OFFICIAL_PROJECT"
  if [ "$DO_LEGACY" = true ]; then
    echo "  Legacy global: $LEGACY_GLOBAL"
    echo "  Legacy project: $LEGACY_PROJECT"
  fi
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

# Handle non-install modes first
case "${MODE:-global}" in
  check)
    check_mode
    exit 0
    ;;
  doctor)
    doctor_mode
    exit 0
    ;;
  dry-run)
    dry_run_mode
    exit 0
    ;;
  diff)
    diff_mode
    exit 0
    ;;
esac

# --- Install mode ---
OFFICIAL_GLOBAL="$CONFIG_DIR/agents"
OFFICIAL_PROJECT="$(pwd)/.opencode/agents"
LEGACY_GLOBAL="$CONFIG_DIR/agent"
LEGACY_PROJECT="$(pwd)/.opencode/agent"

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
  if [ "$DO_LEGACY" = true ]; then
    if [ "$MODE" = "global" ] || [ "$MODE" = "both" ]; then
      targets+=("$LEGACY_GLOBAL")
      labels+=("global legacy")
    fi
    if [ "$MODE" = "project" ] || [ "$MODE" = "both" ]; then
      targets+=("$LEGACY_PROJECT")
      labels+=("project legacy")
    fi
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

  # Install to all official + legacy paths
  MODE="both"
  DO_LEGACY=true
  do_install

  # Write project json config
  echo "=== Project JSON config ==="
  write_json_config "$(pwd)/opencode.json" ".opencode/agents"
  echo ""

  # Run doctor
  echo "=== Doctor diagnostics ==="
  doctor_mode
  echo ""
  echo "If opencode agent list shows the custom agents but the current browser tab does not,"
  echo "start a new OpenCode session from the same project folder."
  echo "Existing web sessions may have loaded the old agent registry."
  exit 0
fi

do_install

# --- JSON config mode ---
if [ "$DO_CONFIG_GLOBAL" = true ]; then
  echo ""
  echo "=== Global JSON config ==="
  write_json_config "$CONFIG_DIR/opencode.json" "./agents" "${DEFAULT_AGENT:-}"
fi

if [ "$DO_CONFIG_PROJECT" = true ]; then
  echo ""
  echo "=== Project JSON config ==="
  write_json_config "$(pwd)/opencode.json" ".opencode/agents" "${DEFAULT_AGENT:-}"
fi

echo ""
echo "Done. Official OpenCode build and plan agents were not modified."
echo ""
echo "If OpenCode is already open, start a new OpenCode session from the same user/project so the UI reloads custom agents."
echo ""
echo "Need troubleshooting? Run: ./agent.sh --doctor"
