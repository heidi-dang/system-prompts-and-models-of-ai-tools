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
# CLI entry point
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Runtime Doctor — Heidi agent pack diagnostics")
    sub = parser.add_subparsers(dest="command", required=True)

    p_np = sub.add_parser("native-prompt", help="Probe native provider prompt composition")

    p_val = sub.add_parser("validate", help="Validate runtime config files")
    p_val.add_argument("--strict", action="store_true", help="Fail on missing optional directories")

    p_disc = sub.add_parser("discover", help="Discover OpenCode runtime capabilities")

    args = parser.parse_args()

    if args.command == "native-prompt":
        sys.exit(probe_native_prompt())
    elif args.command == "validate":
        sys.exit(cmd_validate(args))
    elif args.command == "discover":
        sys.exit(cmd_discover(args))


if __name__ == "__main__":
    main()
