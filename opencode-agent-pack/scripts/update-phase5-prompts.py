#!/usr/bin/env python3
"""Update agent prompts with Phase 5 orchestration rules."""
import os
import re
from pathlib import Path

AGENTS_DIR = "opencode-agent-pack/agents"
SPECIALISTS = ["scout", "planner", "frontend", "backend", "debugger", "auditor"]

HANDOFF_SECTION = """

# Handoff Boundary
Do not spawn or invoke other agents.
If another specialist is needed, return:
## Recommended Handoff
- To:
- Reason:
- Evidence:
- Files affected:
Heidi is the only agent allowed to decide and perform the next delegation.
"""

HEIDI_ORCHESTRATION = """

# Dynamic Subagent Orchestration
Before delegating, choose one orchestration pattern:
- direct
- sequential
- parallel_independent
- audit_after_change
- planner_gate
- debugger_then_specialist

Automatic delegation depth is exactly 1. Specialists must return results to Heidi and must not spawn other agents.

## Task tool identifier rule
When using the Task tool, pass exact agent identifiers without an @ prefix.
Correct:
- scout
- frontend
- backend
- debugger
- auditor
- planner
Incorrect:
- @scout
- @frontend
- @backend
- @debugger
- @auditor
- @planner

## Parallel Execution Rules
Parallel execution is allowed only when:
1. File ownership is clearly separated.
2. No shared migration/schema/config/package-manager file is edited by multiple agents.
3. No single source-of-truth file is edited by multiple agents.
4. Heidi declares ownership boundaries before delegating.
5. Specialists do not edit outside their assigned ownership boundary.
6. Heidi reconciles all specialist output before accepting the result.
7. Heidi runs verification after reconciliation.

Before parallel delegation, declare:
- Strategy:
- Agents:
- Frontend-owned files:
- Backend-owned files:
- Shared/locked files:
- Verification gate:

## Handoff Protocol
Specialists may recommend handoff, but they must not invoke another specialist.
A handoff recommendation must use:
## Recommended Handoff
- To:
- Reason:
- Evidence:
- Files affected:
Heidi decides whether to accept or reject the handoff.

## Forbidden Orchestration Patterns
Do not use:
- recursive delegation
- specialist-to-specialist spawning
- self-invocation
- unbounded group chat
- parallel edits to the same file
- parallel edits to overlapping file areas
- automatic prompt mutation
"""


def append_before_trailing(filepath, section, sentinel=None):
    """Append a section before the trailing content or sentinel marker."""
    content = Path(filepath).read_text(encoding="utf-8")

    # For specialists, append before the last section (after the last ## heading)
    lines = content.split("\n")
    # Find the position of the first anti-patterns or conventions section end
    # Look for the last heading that isn't the main title
    insert_at = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].startswith("# ") and not lines[i].startswith("# Role") and not lines[i].startswith("# Agent"):
            # Insert before this section header
            insert_at = i
            break

    new_content = "\n".join(lines[:insert_at]) + section + "\n" + "\n".join(lines[insert_at:])
    Path(filepath).write_text(new_content, encoding="utf-8")
    return True


def append_to_heidi(filepath):
    """Add orchestration section to heidi.md before 'Project Rules & Memory System'."""
    content = Path(filepath).read_text(encoding="utf-8")

    # Insert the orchestration section after the Task tool identifier rule section
    # and before the Project Rules section
    marker = "# Project Rules & Memory System"
    if marker in content:
        content = content.replace(marker, HEIDI_ORCHESTRATION + "\n" + marker, 1)
    else:
        content += HEIDI_ORCHESTRATION

    Path(filepath).write_text(content, encoding="utf-8")
    return True


def main():
    for name in SPECIALISTS:
        filepath = os.path.join(AGENTS_DIR, f"{name}.md")
        if not os.path.exists(filepath):
            print(f"WARNING: {filepath} not found")
            continue
        append_before_trailing(filepath, HANDOFF_SECTION)
        print(f"Updated: {filepath}")

    # Update heidi.md
    heidi_path = os.path.join(AGENTS_DIR, "heidi.md")
    if os.path.exists(heidi_path):
        append_to_heidi(heidi_path)
        print(f"Updated: {heidi_path}")

    print("\nAll agent prompts updated with Phase 5 orchestration rules.")


if __name__ == "__main__":
    main()
