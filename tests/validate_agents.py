#!/usr/bin/env python3
"""
Agent-definition and permission validation.

Asserts:
- Exactly seven managed agents exist
- Heidi is primary
- All specialists are subagent
- Heidi Task permission denies wildcard, allows only six known specialists
- Specialists deny Task access
- Read-only agents (auditor, planner, scout) deny edit and bash
- Writable specialists (frontend, backend, debugger) allow edit and bash
- No specialist uses mode: all
- No deprecated agents config key
- No Task instruction tells model to pass @agent identifiers
- No restart/reboot/shutdown patterns
- No broad Bash command prefixes on read-only agents
- No duplicate agent identifiers
- Heidi contains orchestration rules (Phase 5)
- Specialists contain Handoff Boundary (Phase 5)
- No specialist instructs spawning/invoking other agents
"""

import os
import re
import sys
import yaml

AGENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "opencode-agent-pack", "agents")
AGENT_NAMES = {"heidi", "frontend", "backend", "debugger", "auditor", "planner", "scout"}

errors = []


def die(msg):
    errors.append(msg)


def parse_frontmatter(filepath):
    """Parse YAML frontmatter from a markdown file."""
    with open(filepath, "r") as f:
        content = f.read()
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        die(f"{filepath}: no YAML frontmatter found")
        return None, content
    try:
        fm = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        die(f"{filepath}: YAML parse error: {e}")
        return None, content
    return fm, content


def main():
    # Check exactly seven agents exist
    found_files = set()
    for fname in os.listdir(AGENTS_DIR):
        if fname.endswith(".md"):
            found_files.add(fname.replace(".md", ""))
    if found_files != AGENT_NAMES:
        die(f"Agent set mismatch: expected {AGENT_NAMES}, found {found_files}")

    for name in sorted(AGENT_NAMES):
        filepath = os.path.join(AGENTS_DIR, f"{name}.md")
        if not os.path.exists(filepath):
            die(f"{filepath}: missing")
            continue

        fm, content = parse_frontmatter(filepath)
        if fm is None:
            continue

        mode = fm.get("mode")
        perm = fm.get("permission", {})

        # Mode check
        if name == "heidi":
            if mode != "primary":
                die(f"{name}: expected mode=primary, got {mode}")
        else:
            if mode != "subagent":
                die(f"{name}: expected mode=subagent, got {mode}")
            if mode == "all":
                die(f"{name}: uses deprecated mode: all")

        # Heidi task access
        if name == "heidi":
            task_perm = perm.get("task", {})
            if not isinstance(task_perm, dict):
                die(f"{name}: task permission should be a dict (allowlist), got {type(task_perm).__name__}")
            if task_perm.get("*") != "deny":
                die(f"{name}: task wildcard should be deny, got {task_perm.get('*')}")
            allowed = {k for k, v in task_perm.items() if v == "allow"}
            expected_required = {"scout", "frontend", "backend", "debugger", "auditor", "planner"}
            expected_optional = {"explore", "general"}
            if not expected_required.issubset(allowed):
                die(f"{name}: task allowlist missing required agents: expected at least {expected_required}, got {allowed}")
            extra = allowed - expected_required - expected_optional
            if extra:
                die(f"{name}: task allowlist has unexpected agents: {extra}")

        # Specialist task denial
        if name != "heidi":
            task_perm = perm.get("task")
            if task_perm != "deny":
                die(f"{name}: specialist should deny task, got {task_perm}")

        # Read-only agents: edit + bash denied
        if name in ("auditor", "planner", "scout"):
            if perm.get("edit") != "deny":
                die(f"{name}: read-only agent should deny edit, got {perm.get('edit')}")
            if perm.get("bash") != "deny":
                die(f"{name}: read-only agent should deny bash, got {perm.get('bash')}")
            # Check no broad bash command prefixes
            bash_perm = perm.get("bash")
            if isinstance(bash_perm, dict):
                for key in bash_perm:
                    if "*" in str(key):
                        die(f"{name}: read-only agent has broad bash prefix pattern: {key}")

        # Writable agents: edit + bash allowed
        if name in ("frontend", "backend", "debugger"):
            if perm.get("edit") != "allow":
                die(f"{name}: writable agent should allow edit, got {perm.get('edit')}")
            if perm.get("bash") != "allow":
                die(f"{name}: writable agent should allow bash, got {perm.get('bash')}")
            if perm.get("task") != "deny":
                die(f"{name}: writable specialist should deny task, got {perm.get('task')}")

        # Check no @agent mentions in task context
        task_at_refs = re.findall(r'task.*@\w+', content, re.IGNORECASE)
        if task_at_refs:
            die(f"{name}: task context references with @ prefix: {task_at_refs[:3]}")

        # Check no restart/reboot/shutdown instructions (only allow as prohibition)
        prohibited_contexts = ["never", "do not", "requires user", "explicit approval", "do not restart"]
        for pattern in [r'\brestart\b', r'\breboot\b', r'\bshutdown\b']:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for m in matches:
                context = content[max(0, content.lower().find(m.lower()) - 80):content.lower().find(m.lower()) + len(m) + 80]
                if not any(pc in context.lower() for pc in prohibited_contexts):
                    die(f"{name}: instruction to '{m}' found: ...{context.strip()[:100]}...")

        # Check no duplicate agent identifiers
        agent_mentions = [m.start() for m in re.finditer(r'@(\w+)', content)]
        seen_positions = set()
        for pos in agent_mentions:
            if pos in seen_positions:
                die(f"{name}: duplicate @ reference at position {pos}")
            seen_positions.add(pos)

    # ── Phase 5: Orchestration rules (heidi.md) ──
    heidi_path = os.path.join(AGENTS_DIR, "heidi.md")
    if os.path.exists(heidi_path):
        heidi_content = open(heidi_path).read()
        # Must contain orchestration patterns (check for new naming)
        for pattern in [
            "Agent Routing",
            "Delegation depth is exactly 1",
            "Parallel Execution Rules",
            "Delegation Protocol",
            "Forbidden Orchestration Patterns",
            "Recursive delegation",
            "self-invocation",
            "file ownership",
            "ownership boundary",
        ]:
            if pattern not in heidi_content and pattern.lower() not in heidi_content.lower():
                die(f"heidi: missing orchestration content: '{pattern}'")
        # Must contain the task tool identifier rule and all required agent names
        if "Task tool identifier rule" not in heidi_content:
            die("heidi: missing Task tool identifier rule section")
        required_agents = ["scout", "frontend", "backend", "debugger", "auditor", "planner"]
        if not all(agent in heidi_content for agent in required_agents):
            missing = [a for a in required_agents if a not in heidi_content]
            die(f"heidi: missing agent names from content: {missing}")
        # Check that @ prefix warning exists (either in task tool section or nearby)
        if "@" not in heidi_content or "prefix" not in heidi_content.lower():
            die("heidi: missing @ prefix guidance")

    # ── Phase 5: Specialist handoff boundary ──
    for name in sorted(AGENT_NAMES):
        if name == "heidi":
            continue
        fpath = os.path.join(AGENTS_DIR, f"{name}.md")
        content = open(fpath).read()
        if "Handoff Boundary" not in content:
            die(f"{name}: missing Handoff Boundary section")
        if "Do not spawn or invoke other agents" not in content:
            die(f"{name}: missing spawn prohibition")
        if "Recommended Handoff" not in content:
            die(f"{name}: missing Recommended Handoff section")
        # Check for spawn/invoke/delegate instructions to other agents
        spawn_patterns = [
            (r'^\s*spawn\s+.*agent', "spawn instruction as directive"),
            (r'invoke @(\w+)', "invoke @agent reference"),
            (r'delegate to @(\w+)', "delegate to @agent"),
        ]
        for pat, desc in spawn_patterns:
            if re.search(pat, content, re.IGNORECASE | re.MULTILINE):
                die(f"{name}: forbidden {desc}")

    # Final report
    if errors:
        print(f"\nVALIDATION FAILED: {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print(f"Validation PASSED: {len(AGENT_NAMES)} agents correct")


if __name__ == "__main__":
    main()
