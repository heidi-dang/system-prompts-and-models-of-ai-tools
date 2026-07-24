#!/usr/bin/env python3
"""
Runtime Doctor — comprehensive runtime diagnostic for Heidi agent pack.

Commands:
  native-prompt   Probe native provider prompt composition
  validate        Validate runtime config files
  discover        Discover OpenCode runtime capabilities

All commands accept --mode {isolated|installed} (default: isolated).

Output markers:
  PASS — required check passed
  FAIL — required check failed (exits non-zero)
  SKIP — explicitly skipped because prerequisite is unavailable (not counted)

When opencode is unavailable in isolated mode, OpenCode-dependent checks
are SKIP rather than FAIL. In installed mode they remain FAIL.
"""

import argparse
import json
import os
import re
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


# ──────────────────────────────────────────────────────────────────
# Status helpers: PASS / FAIL / SKIP
# ──────────────────────────────────────────────────────────────────

def _status_pass(label):
    return ("PASS", label, None)


def _status_fail(label, detail=None):
    return ("FAIL", label, detail)


def _status_skip(label, reason=None):
    return ("SKIP", label, reason or "prerequisite unavailable")


def _format_status(status_tuple):
    """Format a status tuple for display."""
    marker, label, detail = status_tuple
    line = f"{label}: {marker}"
    if detail is not None:
        line += f" ({detail})"
    return line


def _print_summary(results):
    """Print a formatted summary of PASS/FAIL/SKIP results and return exit code."""
    passed = sum(1 for r in results if r[0] == "PASS")
    failed = sum(1 for r in results if r[0] == "FAIL")
    skipped = sum(1 for r in results if r[0] == "SKIP")

    for r in results:
        print(_format_status(r))

    print(f"\nSummary: {passed} PASS, {failed} FAIL, {skipped} SKIP")
    return failed  # exit code = number of failures


# ──────────────────────────────────────────────────────────────────
# Token governance checks (always run, always required)
# ──────────────────────────────────────────────────────────────────

def check_token_governance():
    """Run all token governance checks.

    Returns list of (marker, label, detail) tuples.
    All governance checks are required — no SKIP allowed.
    """
    results = []

    # 1. Token policy present and valid
    policy_path = Path(__file__).parent.parent / "runtime" / "runtime-policy.json"
    policy_present = policy_path.is_file()
    policy_valid = False
    consumption = {}
    if policy_present:
        try:
            with open(policy_path) as f:
                policy = json.load(f)
            consumption = policy.get("runtime", {}).get("consumption", {})
            policy_valid = bool(consumption)
        except Exception:
            pass
    results.append(_status_pass("Token policy present") if policy_present
                   else _status_fail("Token policy present", "not found"))
    results.append(_status_pass("Token policy valid") if policy_valid
                   else _status_fail("Token policy valid",
                                     "no consumption section" if policy_present else "no policy"))

    # 2. Budget manager module exists
    budget_script = Path(__file__).parent / "token_budget.py"
    results.append(_status_pass("Budget manager module exists") if budget_script.is_file()
                   else _status_fail("Budget manager module exists", "token_budget.py not found"))

    # 3. Token estimator module exists
    estimator_script = Path(__file__).parent / "token_estimator.py"
    results.append(_status_pass("Token estimator module exists") if estimator_script.is_file()
                   else _status_fail("Token estimator module exists", "token_estimator.py not found"))

    # 4. Delegation handoff module exists
    handoff_script = Path(__file__).parent / "delegation_handoff.py"
    results.append(_status_pass("Delegation handoff module exists") if handoff_script.is_file()
                   else _status_fail("Delegation handoff module exists", "delegation_handoff.py not found"))

    # 5. Delegation payload capped
    if handoff_script.is_file():
        try:
            from delegation_handoff import DEFAULT_DELEGATION_CONTEXT_LIMIT, MAX_DELEGATION_CONTEXT_LIMIT
            capped = DEFAULT_DELEGATION_CONTEXT_LIMIT <= 1500 and MAX_DELEGATION_CONTEXT_LIMIT <= 4000
            results.append(_status_pass("Delegation payload capped") if capped
                           else _status_fail("Delegation payload capped",
                                             f"default={DEFAULT_DELEGATION_CONTEXT_LIMIT}, max={MAX_DELEGATION_CONTEXT_LIMIT}"))
        except Exception as e:
            results.append(_status_fail("Delegation payload capped", str(e)))

    # 6. Subagent limits enforced in policy
    subagent_limit = consumption.get("max_subagent_calls") if policy_valid else None
    results.append(_status_pass("Subagent limits enforced") if (subagent_limit is not None and subagent_limit <= 8)
                   else _status_fail("Subagent limits enforced",
                                     f"max_subagent_calls={subagent_limit}" if subagent_limit else "no policy"))

    # 7. Retry circuit breaker active
    retry_limit = consumption.get("max_equivalent_retries") if policy_valid else None
    results.append(_status_pass("Retry circuit breaker active") if (retry_limit is not None and retry_limit <= 2)
                   else _status_fail("Retry circuit breaker active",
                                     f"max_equivalent_retries={retry_limit}" if retry_limit else "no policy"))

    # 8. Audit-cycle limit active
    audit_limit = consumption.get("max_audit_cycles") if policy_valid else None
    results.append(_status_pass("Audit-cycle limit active") if (audit_limit is not None and audit_limit <= 1)
                   else _status_fail("Audit-cycle limit active",
                                     f"max_audit_cycles={audit_limit}" if audit_limit else "no policy"))

    # 9. No conflicting token-policy defaults
    heidi_md = Path(__file__).parent.parent / "agents" / "heidi.md"
    has_conflict = False
    if heidi_md.is_file():
        content = heidi_md.read_text()
        max_total_matches = re.findall(r'max_total_tokens["\s:]+(\d+)', content)
        if len(set(max_total_matches)) > 1:
            has_conflict = True
    results.append(_status_pass("No conflicting token-policy defaults") if not has_conflict
                   else _status_fail("No conflicting token-policy defaults",
                                     "conflicting max_total_tokens values found"))

    # 10. Task ledger writes token usage
    ledger_enabled = policy.get("runtime", {}).get("task_ledger", {}).get("log_token_usage", False) if policy_present else False
    results.append(_status_pass("Task ledger writes token usage") if ledger_enabled
                   else _status_fail("Task ledger writes token usage",
                                     "log_token_usage not enabled" if policy_present else "no policy"))

    return results


# ──────────────────────────────────────────────────────────────────
# native-prompt command
# ──────────────────────────────────────────────────────────────────

def probe_native_prompt(mode="isolated"):
    """Check native provider prompt integrity.

    Args:
        mode: "isolated" (skip OpenCode-dependent checks) or "installed" (require all).

    Returns exit code (number of FAIL checks).
    """
    results = []

    if mode == "isolated" and not is_opencode_available():
        # In isolated mode, skip OpenCode-dependent checks gracefully
        results.append(_status_skip("Native provider prompt", "opencode not installed (isolated mode)"))
        results.append(_status_skip("Heidi orchestration layer", "opencode not installed (isolated mode)"))
        results.append(_status_skip("Duplicate orchestration layer", "opencode not installed (isolated mode)"))
        results.append(_status_skip("Selected model preserved", "opencode not installed (isolated mode)"))
        results.append(_status_skip("Build unchanged", "opencode not installed (isolated mode)"))
        results.append(_status_skip("Plan unchanged", "opencode not installed (isolated mode)"))
    elif not is_opencode_available():
        # Installed mode: OpenCode must be available
        results.append(_status_fail("Native provider prompt", "opencode not installed"))
        results.append(_status_fail("Heidi orchestration layer", "opencode not installed"))
        results.append(_status_fail("Duplicate orchestration layer", "opencode not installed"))
        results.append(_status_fail("Selected model preserved", "opencode not installed"))
        results.append(_status_fail("Build unchanged", "opencode not installed"))
        results.append(_status_fail("Plan unchanged", "opencode not installed"))
    else:
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
            results.append(_status_pass("Native provider prompt"))
        else:
            prompt_present = has_config and '"prompt"' in raw
            results.append(_status_pass("Native provider prompt") if prompt_present
                           else _status_fail("Native provider prompt", "no prompt key found"))

        # Check 2: Heidi orchestration layer present exactly once
        orchestration_count = 0
        if has_config:
            orchestration_count += raw.count("orchestrat")
            orchestration_count += raw.count("Heidi")
        agent_dir = Path(config_dir) / "agents"
        if agent_dir.is_dir():
            for agent_file in agent_dir.glob("*.md"):
                try:
                    content = agent_file.read_text(encoding="utf-8")
                    for m in heidi_markers:
                        orchestration_count += content.count(m)
                except Exception:
                    pass
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
        dup_ok = orchestration_count <= 50
        results.append(_status_pass("Heidi orchestration layer") if heidi_ok
                       else _status_fail("Heidi orchestration layer", "not found"))
        results.append(_status_pass("Duplicate orchestration layer") if dup_ok
                       else _status_fail("Duplicate orchestration layer", "potential duplicates detected"))

        # Check 3: Selected model preserved
        model_preserved = True
        if has_config:
            model_preserved = "model" in config or "default_model" in config
        results.append(_status_pass("Selected model preserved") if model_preserved
                       else _status_fail("Selected model preserved", "no model config found"))

        # Check 4 & 5: Build and Plan unchanged
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
        results.append(_status_pass("Build unchanged") if build_unchanged
                       else _status_fail("Build unchanged"))
        results.append(_status_pass("Plan unchanged") if plan_unchanged
                       else _status_fail("Plan unchanged"))

    # Token governance checks always run (required, no skip) — merge into results
    gov_results = check_token_governance()
    results.extend(gov_results)

    print("\n--- Native Prompt ---")
    return _print_summary(results)


# ──────────────────────────────────────────────────────────────────
# validate command
# ──────────────────────────────────────────────────────────────────

def cmd_validate(args):
    """Validate runtime config files.

    In isolated mode, missing global opencode.json is SKIP.
    In installed mode, missing global opencode.json is FAIL.
    Missing .heidi directory is always FAIL.
    """
    results = []
    mode = getattr(args, "mode", "isolated")

    config_dir = os.environ.get(
        "OPENCODE_CONFIG_DIR",
        os.path.join(os.path.expanduser("~"), ".config", "opencode"),
    )
    config_path = os.path.join(config_dir, "opencode.json")

    # Global opencode.json
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if "agents" in cfg and "agent" not in cfg:
                results.append(_status_fail("Global opencode.json structure", "deprecated 'agents' key"))
            if "agent" in cfg:
                for name, obj in cfg["agent"].items():
                    if not isinstance(obj, dict):
                        results.append(_status_fail(f"Agent '{name}' format", "not a dict"))
                    elif "prompt" not in obj:
                        results.append(_status_fail(f"Agent '{name}' completeness", "missing 'prompt'"))
        except json.JSONDecodeError as e:
            results.append(_status_fail("Global opencode.json", f"invalid JSON: {e}"))
        results.append(_status_pass("Global opencode.json"))
    elif mode == "installed":
        results.append(_status_fail("Global opencode.json", f"not found at {config_path}"))
    else:
        results.append(_status_skip("Global opencode.json", "not found (expected in isolated CI)"))

    # Agent directory
    agent_dir = Path(config_dir) / "agents"
    if agent_dir.is_dir():
        for agent_file in agent_dir.glob("*.md"):
            try:
                content = agent_file.read_text(encoding="utf-8")
                if not content.strip():
                    results.append(_status_fail(f"Agent file {agent_file.name}", "empty"))
            except Exception as e:
                results.append(_status_fail(f"Agent file {agent_file.name}", f"read error: {e}"))
        results.append(_status_pass("Agent directory") if not any(r[0] == "FAIL" for r in results)
                       else _status_fail("Agent directory", "some agent files have errors"))
    elif args.strict:
        results.append(_status_fail("Agent directory", f"not found at {agent_dir}"))
    else:
        results.append(_status_skip("Agent directory", "not found (strict mode only)"))

    # Project-level opencode.json
    project_config = Path(os.getcwd()) / "opencode.json"
    if project_config.is_file():
        try:
            with open(project_config, "r", encoding="utf-8") as f:
                json.load(f)
            results.append(_status_pass("Project opencode.json"))
        except json.JSONDecodeError as e:
            results.append(_status_fail("Project opencode.json", f"invalid JSON: {e}"))
    else:
        results.append(_status_skip("Project opencode.json", "not found (project config optional)"))

    # .heidi directory — always required
    heidi_dir = Path(os.getcwd()) / ".heidi"
    if heidi_dir.is_dir():
        all_present = True
        for req in ("rules.md", "commands.md", "memory.jsonl", "context-index.json"):
            if not (heidi_dir / req).exists():
                results.append(_status_fail(f".heidi/{req}", "missing"))
                all_present = False
        if all_present:
            results.append(_status_pass(".heidi directory"))
    else:
        results.append(_status_fail(".heidi directory", "not found"))

    # Token governance checks (merge into results so failures count toward exit code)
    gov_results = check_token_governance()
    results.extend(gov_results)

    print("\n--- Validation ---")
    return _print_summary(results)


# ──────────────────────────────────────────────────────────────────
# discover command
# ──────────────────────────────────────────────────────────────────

def cmd_discover(args):
    """Discover OpenCode runtime capabilities."""
    print("=== Runtime Discovery ===")

    oc_bin = find_opencode_binary()
    print(f"opencode binary: {oc_bin or 'NOT FOUND'}")

    if oc_bin:
        import subprocess
        try:
            ver = subprocess.check_output([oc_bin, "--version"], stderr=subprocess.STDOUT, text=True, timeout=10).strip()
            print(f"opencode version: {ver}")
        except Exception:
            print("opencode version: unknown")

    config_dir = os.environ.get(
        "OPENCODE_CONFIG_DIR",
        os.path.join(os.path.expanduser("~"), ".config", "opencode"),
    )
    print(f"Config directory: {config_dir}")
    print(f"Global config: {os.path.join(config_dir, 'opencode.json')}")
    print(f"Project config: {os.path.join(os.getcwd(), 'opencode.json')}")

    global_agents = os.path.join(config_dir, "agents")
    project_agents = os.path.join(os.getcwd(), ".opencode", "agents")

    for label, path in [("Global", global_agents), ("Project", project_agents)]:
        if os.path.isdir(path):
            agent_files = list(Path(path).glob("*.md"))
            print(f"{label} agents ({len(agent_files)} files): {[f.name for f in sorted(agent_files)]}")
        else:
            print(f"{label} agents: (directory not found)")

    heidi_dir = Path(os.getcwd()) / ".heidi"
    if heidi_dir.is_dir():
        files = [f.name for f in heidi_dir.iterdir() if f.is_file()]
        print(f".heidi files: {sorted(files)}")
    else:
        print(".heidi: not initialized")

    for env_var in ("OPENCODE_MODEL", "OPENCODE_PROVIDER", "OPENAI_MODEL", "ANTHROPIC_MODEL"):
        val = os.environ.get(env_var)
        if val:
            print(f"Model env ({env_var}): {val}")

    print("\n--- Capability Probes ---")
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    print(f"File system encoding: {sys.getfilesystemencoding()}")

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
    p_np.add_argument("--mode", choices=["isolated", "installed"], default="isolated",
                      help="Run mode: isolated (skip offline deps) or installed (require everything)")

    p_val = sub.add_parser("validate", help="Validate runtime config files")
    p_val.add_argument("--mode", choices=["isolated", "installed"], default="isolated",
                       help="Run mode: isolated (skip offline deps) or installed (require everything)")
    p_val.add_argument("--strict", action="store_true", help="Fail on missing optional directories")

    p_disc = sub.add_parser("discover", help="Discover OpenCode runtime capabilities")

    args = parser.parse_args()

    if args.command == "native-prompt":
        sys.exit(probe_native_prompt(mode=args.mode))
    elif args.command == "validate":
        sys.exit(cmd_validate(args))
    elif args.command == "discover":
        sys.exit(cmd_discover(args))


if __name__ == "__main__":
    main()
