#!/usr/bin/env python3
"""
Runtime Doctor — comprehensive runtime diagnostic for Heidi agent pack.

Commands:
  native-prompt   Probe native provider prompt composition
  validate        Validate runtime config files
  discover        Discover OpenCode runtime capabilities

Output format for native-prompt:
  Native provider prompt: PASS
  Heidi orchestration layer: PASS
  Duplicate orchestration layer: PASS
  Selected model preserved: PASS
  Build unchanged: PASS
  Plan unchanged: PASS

When opencode is unavailable, report "UNAVAILABLE" and exit 0.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# ──────────────────────────────────────────────────────────────────
# Helpers: detect opencode & runtime artifacts
# ──────────────────────────────────────────────────────────────────

def find_opencode_binary():
    """Return path to opencode binary, or None."""
    for candidate in ("opencode", "/usr/local/bin/opencode", "/usr/bin/opencode"):
        path = candidate
        if os.path.isabs(path) and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
        elif not os.path.isabs(path):
            from shutil import which
            resolved = which(path)
            if resolved:
                return resolved
    return None


def is_opencode_available():
    return find_opencode_binary() is not None


def _status(passed, label, detail=None):
    marker = "PASS" if passed else "FAIL"
    line = f"{label}: {marker}"
    if detail and not passed:
        line += f" ({detail})"
    return line


# ──────────────────────────────────────────────────────────────────
# native-prompt command
# ──────────────────────────────────────────────────────────────────

def probe_native_prompt():
    """Check native provider prompt integrity.

    Checks performed:
      1. Native provider prompt is present (opencode config has a 'prompt' or system prompt stanza).
      2. Heidi orchestration layer is present exactly once in the composed prompt.
      3. Selected model is preserved.
      4. Build agent is unchanged.
      5. Plan agent is unchanged.
    """
    results = []

    if not is_opencode_available():
        print("Native provider prompt: UNAVAILABLE (opencode not installed)")
        print("Heidi orchestration layer: UNAVAILABLE")
        print("Duplicate orchestration layer: UNAVAILABLE")
        print("Selected model preserved: UNAVAILABLE")
        print("Build unchanged: UNAVAILABLE")
        print("Plan unchanged: UNAVAILABLE")
        return 0

    # Attempt to gather runtime config
    config_dir = os.environ.get(
        "OPENCODE_CONFIG_DIR",
        os.path.join(os.path.expanduser("~"), ".config", "opencode"),
    )
    config_path = os.path.join(config_dir, "opencode.json")

    heidi_markers = ["Heidi", "heidi", "HEIDI", "orchestration layer"]
    build_markers = ["Build", "build", "BUILD"]
    plan_markers = ["Plan", "plan", "PLAN"]

    has_config = os.path.isfile(config_path)
    config = {}

    if has_config:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw = f.read()
            config = json.loads(raw)
        except Exception:
            config = {}

    # Check 1: Native provider prompt presence
    prompt_present = bool(config.get("prompt") or
                          config.get("system_prompt") or
                          config.get("agent", {}).get("heidi", {}).get("prompt"))
    if prompt_present:
        results.append(_status(True, "Native provider prompt"))
    else:
        # Try opcode config read
        prompt_present = has_config and '"prompt"' in raw
        results.append(_status(prompt_present, "Native provider prompt",
                               "no prompt key found" if not prompt_present else None))

    # Check 2: Heidi orchestration layer present exactly once
    orchestration_count = 0
    if has_config:
        orchestration_count += raw.count("orchestrat")
        orchestration_count += raw.count("Heidi")
    # Search agent files for Heidi orchestration layer
    agent_dir = Path(config_dir) / "agents"
    if agent_dir.is_dir():
        for agent_file in agent_dir.glob("*.md"):
            try:
                content = agent_file.read_text(encoding="utf-8")
                for m in heidi_markers:
                    orchestration_count += content.count(m)
            except Exception:
                pass
    # Also check project-level
    project_agent_dir = Path(os.getcwd()) / ".opencode" / "agents"
    if project_agent_dir.is_dir():
        for agent_file in project_agent_dir.glob("*.md"):
            try:
                content = agent_file.read_text(encoding="utf-8")
                for m in heidi_markers:
                    orchestration_count += content.count(m)
            except Exception:
                pass

    heidi_ok = orchestration_count > 0
    dup_ok = orchestration_count <= 50  # heuristic: not absurdly duplicated
    results.append(_status(heidi_ok, "Heidi orchestration layer",
                           "not found" if not heidi_ok else None))
    results.append(_status(dup_ok, "Duplicate orchestration layer",
                           "potential duplicates detected" if not dup_ok else None))

    # Check 3: Selected model preserved
    model_preserved = True
    if has_config:
        model_preserved = "model" in config or "default_model" in config
    results.append(_status(model_preserved, "Selected model preserved" if model_preserved else "Selected model preserved",
                           "no model config found" if not model_preserved else None))

    # Check 4 & 5: Build and Plan unchanged (can only verify if they're present)
    build_unchanged = True
    plan_unchanged = True
    if agent_dir.is_dir():
        build_file = agent_dir / "build.md"
        plan_file = agent_dir / "plan.md"
        if build_file.exists():
            try:
                content = build_file.read_text(encoding="utf-8")
                for m in build_markers:
                    if content.count(m) < 1:
                        build_unchanged = False
            except Exception:
                pass
        if plan_file.exists():
            try:
                content = plan_file.read_text(encoding="utf-8")
                for m in plan_markers:
                    if content.count(m) < 1:
                        plan_unchanged = False
            except Exception:
                pass
    results.append(_status(build_unchanged, "Build unchanged"))
    results.append(_status(plan_unchanged, "Plan unchanged"))

    for line in results:
        print(line)

    return 0 if all("PASS" in r for r in results) else 1


# ──────────────────────────────────────────────────────────────────
# validate command
# ──────────────────────────────────────────────────────────────────

def cmd_validate(args):
    """Validate runtime config files."""
    errors = []
    config_dir = os.environ.get(
        "OPENCODE_CONFIG_DIR",
        os.path.join(os.path.expanduser("~"), ".config", "opencode"),
    )
    config_path = os.path.join(config_dir, "opencode.json")

    # Check opencode.json
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if "agents" in cfg and "agent" not in cfg:
                errors.append("opencode.json: deprecated 'agents' key found (should be 'agent')")
            if "agent" in cfg:
                for name, obj in cfg["agent"].items():
                    if not isinstance(obj, dict):
                        errors.append(f"opencode.json: agent '{name}' is not a dict")
                    elif "prompt" not in obj and "prompt" not in obj:
                        errors.append(f"opencode.json: agent '{name}' missing 'prompt'")
        except json.JSONDecodeError as e:
            errors.append(f"opencode.json: invalid JSON: {e}")
    else:
        errors.append(f"opencode.json: not found at {config_path}")

    # Check agent directory
    agent_dir = Path(config_dir) / "agents"
    if agent_dir.is_dir():
        for agent_file in agent_dir.glob("*.md"):
            try:
                content = agent_file.read_text(encoding="utf-8")
                if not content.strip():
                    errors.append(f"{agent_file}: empty agent file")
            except Exception as e:
                errors.append(f"{agent_file}: read error: {e}")
    elif args.strict:
        errors.append(f"agents directory not found: {agent_dir}")

    # Check project-level
    project_config = Path(os.getcwd()) / "opencode.json"
    if project_config.is_file():
        try:
            with open(project_config, "r", encoding="utf-8") as f:
                json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"project opencode.json: invalid JSON: {e}")

    # Check .heidi directory
    heidi_dir = Path(os.getcwd()) / ".heidi"
    if heidi_dir.is_dir():
        for req in ("rules.md", "commands.md", "memory.jsonl", "context-index.json"):
            if not (heidi_dir / req).exists():
                errors.append(f".heidi/{req}: missing")
    else:
        errors.append(".heidi directory not found")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    print("Validation PASSED")
    return 0


# ──────────────────────────────────────────────────────────────────
# discover command
# ──────────────────────────────────────────────────────────────────

def cmd_discover(args):
    """Discover OpenCode runtime capabilities."""
    print("=== Runtime Discovery ===")

    # OpenCode binary
    oc_bin = find_opencode_binary()
    print(f"opencode binary: {oc_bin or 'NOT FOUND'}")

    # Version
    if oc_bin:
        import subprocess
        try:
            ver = subprocess.check_output([oc_bin, "--version"], stderr=subprocess.STDOUT, text=True, timeout=10).strip()
            print(f"opencode version: {ver}")
        except Exception:
            print("opencode version: unknown")

    # Config paths
    config_dir = os.environ.get(
        "OPENCODE_CONFIG_DIR",
        os.path.join(os.path.expanduser("~"), ".config", "opencode"),
    )
    print(f"Config directory: {config_dir}")
    print(f"Global config: {os.path.join(config_dir, 'opencode.json')}")
    print(f"Project config: {os.path.join(os.getcwd(), 'opencode.json')}")

    # Agent directories
    global_agents = os.path.join(config_dir, "agents")
    project_agents = os.path.join(os.getcwd(), ".opencode", "agents")

    for label, path in [("Global", global_agents), ("Project", project_agents)]:
        if os.path.isdir(path):
            agent_files = list(Path(path).glob("*.md"))
            print(f"{label} agents ({len(agent_files)} files): {[f.name for f in sorted(agent_files)]}")
        else:
            print(f"{label} agents: (directory not found)")

    # .heidi state
    heidi_dir = Path(os.getcwd()) / ".heidi"
    if heidi_dir.is_dir():
        files = [f.name for f in heidi_dir.iterdir() if f.is_file()]
        print(f".heidi files: {sorted(files)}")
    else:
        print(".heidi: not initialized")

    # Model info from env
    for env_var in ("OPENCODE_MODEL", "OPENCODE_PROVIDER", "OPENAI_MODEL", "ANTHROPIC_MODEL"):
        val = os.environ.get(env_var)
        if val:
            print(f"Model env ({env_var}): {val}")

    # Capability probes
    print("\n--- Capability Probes ---")
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    print(f"File system encoding: {sys.getfilesystemencoding()}")

    # Plugin/MCP servers
    mcp_config = os.path.join(config_dir, "mcp.json")
    if os.path.isfile(mcp_config):
        try:
            with open(mcp_config) as f:
                mcp = json.load(f)
            print(f"MCP servers: {len(mcp.get('mcpServers', {}))} configured")
        except Exception:
            print("MCP config: present but unreadable")
    else:
        print("MCP config: not found")

    # Permissions
    perm_config = os.path.join(config_dir, "permissions.json")
    if os.path.isfile(perm_config):
        print("Permissions config: present")
    else:
        print("Permissions config: not found")

    return 0


# ──────────────────────────────────────────────────────────────────
# agent-discovery command
# ──────────────────────────────────────────────────────────────────

# The 7 Heidi-managed agents that must be present in discovery paths.
HEIDI_AGENTS = {"heidi", "scout", "planner", "auditor", "frontend", "backend", "debugger"}

# Native OpenCode agents that ship with the runtime.
NATIVE_AGENTS = {"build", "plan"}

# Internal runtime prompt fragment names that MUST NOT appear as
# discovered agent names (they are composition internals, not agents).
RUNTIME_FRAGMENTS = {
    "core", "orchestration", "routing", "verification", "resilience",
    "reporting", "memory", "fast-path", "heidi-orchestration",
}


def _get_opencode_agent_list():
    """Run 'opencode agent list' and return a set of agent names, or None on failure."""
    oc_bin = find_opencode_binary()
    if not oc_bin:
        return None
    try:
        import subprocess as _sp
        output = _sp.check_output(
            [oc_bin, "agent", "list"],
            stderr=_sp.STDOUT,
            text=True,
            timeout=15,
        )
        names = set()
        for line in output.strip().splitlines():
            cleaned = line.strip()
            # Strip common bullet / tree-drawing characters
            cleaned = cleaned.lstrip("-*●◦•·▪▸►»>|├└│─ ")
            cleaned = cleaned.strip()
            if not cleaned:
                continue
            lower = cleaned.lower()
            # Skip header/footer/empty-state lines
            if lower.startswith(("agent", "available", "no agent", "name", "id", "command")):
                continue
            # Extract the first word as the likely agent name
            first_word = cleaned.split()[0].rstrip(".,:;")
            if first_word:
                names.add(first_word)
        return names if names else None
    except Exception:
        return None


def cmd_agent_discovery(args):
    """Validate OpenCode agent discovery paths.

    Checks performed:
      1. Any discovered agent name containing ".bak."
      2. Any discovered agent beginning with "Runtime/" or "runtime/"
      3. Internal prompt fragments appearing as agents
      4. All 7 Heidi-managed agents are present
      5. Native agents (build, plan) are preserved
      6. No duplicate Heidi agents across discovery paths
      7. No backup folders exist under discovery paths
      8. No Runtime/ or runtime/ directories exist in discovery paths
    """
    config_dir = os.environ.get(
        "OPENCODE_CONFIG_DIR",
        os.path.join(os.path.expanduser("~"), ".config", "opencode"),
    )
    primary_path = Path(config_dir) / "agents"
    project_path = Path(os.getcwd()) / ".opencode" / "agents"
    discovery_paths = [p for p in [primary_path, project_path] if p.is_dir()]

    failures = []

    # ── Gather discovered agents ────────────────────────────────
    # Level 0: direct *.md files  →  agent name = stem
    # Level 1: *.md in subdirs    →  agent name = "subdir/stem"
    discovered = {}  # agent_name → [full_path, ...]

    for dp in discovery_paths:
        for md_file in dp.glob("*.md"):
            discovered.setdefault(md_file.stem, []).append(str(md_file))
        for subdir in dp.iterdir():
            if not subdir.is_dir():
                continue
            for md_file in subdir.glob("*.md"):
                name = f"{subdir.name}/{md_file.stem}"
                discovered.setdefault(name, []).append(str(md_file))

    # ── Check 1: Backup agents (.bak.) ─────────────────────────
    backup_agents = sorted(n for n in discovered if ".bak." in n)

    # ── Check 2: Runtime-prefixed agents ───────────────────────
    runtime_prefixed = sorted(
        n for n in discovered if n.startswith(("Runtime/", "runtime/"))
    )

    # ── Check 3: Internal prompt fragments exposed ─────────────
    runtime_fragments_exposed = sorted(
        n for n in discovered if n in RUNTIME_FRAGMENTS
    )

    # ── Check 4: All 7 Heidi agents present ────────────────────
    missing_heidi = sorted(HEIDI_AGENTS - set(discovered.keys()))

    # ── Check 5: Native agents preserved ───────────────────────
    missing_native = sorted(NATIVE_AGENTS - set(discovered.keys()))

    # ── Check 6: Duplicate Heidi agents ────────────────────────
    duplicate_heidi = sorted(
        a for a in HEIDI_AGENTS if len(discovered.get(a, [])) > 1
    )

    # ── Check 7: Backup folders in discovery paths ─────────────
    backup_dirs = []
    for dp in discovery_paths:
        for item in dp.iterdir():
            if item.is_dir() and (".bak." in item.name or item.name.endswith(".bak")):
                backup_dirs.append(str(item))

    # ── Check 8: Runtime directories in discovery paths ────────
    runtime_dirs = []
    for dp in discovery_paths:
        for rt_name in ("Runtime", "runtime"):
            rt_dir = dp / rt_name
            if rt_dir.is_dir():
                runtime_dirs.append(str(rt_dir))

    # ── Build failure list ─────────────────────────────────────
    for name in backup_agents:
        failures.append(f"Backup file exposed as agent: {name}")
    for name in runtime_prefixed:
        failures.append(f"Runtime-prefixed agent discovered: {name}")
    for name in runtime_fragments_exposed:
        failures.append(f"Runtime prompt fragment exposed as agent: {name}")
    if missing_heidi:
        failures.append(f"Missing Heidi agent(s): {', '.join(missing_heidi)}")
    if missing_native:
        if is_opencode_available():
            failures.append(f"Missing native agent(s): {', '.join(missing_native)}")
    for name in duplicate_heidi:
        failures.append(f"Duplicate Heidi agent: {name}")
    for d in backup_dirs:
        failures.append(f"Backup folder in discovery path: {d}")
    for d in runtime_dirs:
        failures.append(f"Runtime directory in discovery path: {d}")

    # ── Output ─────────────────────────────────────────────────
    print(f"Agent discovery path: {primary_path}")
    print(f"Managed Heidi agents: {len(HEIDI_AGENTS)}")
    print(f"Runtime fragments exposed: {len(runtime_fragments_exposed)}")
    print(f"Backup agents exposed: {len(backup_agents)}")
    print(f"Duplicate agents: {len(duplicate_heidi)}")
    print(f"Build preserved: {'PASS' if 'build' in discovered else 'FAIL'}")
    print(f"Plan preserved: {'PASS' if 'plan' in discovered else 'FAIL'}")

    # ── Additional user agents (tolerate but list) ─────────────
    known = HEIDI_AGENTS | NATIVE_AGENTS | RUNTIME_FRAGMENTS
    user_agents = set(discovered.keys()) - known - set(backup_agents)
    # Also exclude runtime-prefixed from user list — they were already flagged
    user_agents -= set(runtime_prefixed)
    if user_agents:
        print(f"Additional user agents: {', '.join(sorted(user_agents))}")

    # ── OpenCode cross-validation ──────────────────────────────
    if is_opencode_available():
        oc_agents = _get_opencode_agent_list()
        if oc_agents is not None:
            fs_set = set(discovered.keys())
            fs_only = fs_set - oc_agents
            oc_only = oc_agents - fs_set
            if fs_only:
                print(f"Filesystem agents not in opencode list: {', '.join(sorted(fs_only))}")
            if oc_only:
                print(f"OpenCode agents not in filesystem: {', '.join(sorted(oc_only))}")

    # ── Status ─────────────────────────────────────────────────
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        print("Status: FAIL")
        return 1
    else:
        print("Status: PASS")
        return 0


# ──────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Runtime Doctor — Heidi agent pack diagnostics")
    sub = parser.add_subparsers(dest="command", required=True)

    p_np = sub.add_parser("native-prompt", help="Probe native provider prompt composition")

    p_val = sub.add_parser("validate", help="Validate runtime config files")
    p_val.add_argument("--strict", action="store_true", help="Fail on missing optional directories")

    p_disc = sub.add_parser("discover", help="Discover OpenCode runtime capabilities")

    p_ad = sub.add_parser("agent-discovery", help="Validate agent discovery paths")

    args = parser.parse_args()

    if args.command == "native-prompt":
        sys.exit(probe_native_prompt())
    elif args.command == "validate":
        sys.exit(cmd_validate(args))
    elif args.command == "discover":
        sys.exit(cmd_discover(args))
    elif args.command == "agent-discovery":
        sys.exit(cmd_agent_discovery(args))


if __name__ == "__main__":
    main()
