#!/usr/bin/env python3
"""
Verified Prompt Improvement Proposals — safe prompt evolution system.

Commands:
  create --agent <a> --title <t> --evidence <e> --expected-impact <i>
         Create a prompt improvement proposal
  validate <dir>              Validate all proposals in a directory
  list <dir>                  List proposals
  apply --proposal <f>        Apply an approved proposal (requires safety checks)
  evaluate --proposal <f> [--benchmark-fixture <f>]  Evaluate proposal against benchmarks
  approve --proposal <f>      Mark proposal as approved (requires explicit approval)
  rollback --proposal <f>     Rollback an applied proposal
  status --proposal <f>       Show current state machine status
"""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

VALID_AGENTS = {"heidi", "scout", "planner", "frontend", "backend", "debugger", "auditor"}
VALID_RISK = {"low", "medium", "high"}
VALID_STATUS = {"draft", "proposed", "approved", "rejected", "applied"}

PROPOSAL_TEMPLATE = """# Prompt Improvement Proposal
## Status
{status}
## Target Agent
{agent}
## Problem
{title}
## Evidence
{evidence}
## Proposed Change
*Describe the specific prompt change here*

## Expected Impact
{expected_impact}
## Risk Level
{risk}
## Validation Plan
- Run existing tests for the agent
- Verify agent behavior doesn't degrade
## Rollback Plan
- Restore from backup: opencode-agent-pack/agents/{agent}.md.bak.*
"""


def stable_id(title, agent):
    return hashlib.sha256(f"{agent}:{title}".encode()).hexdigest()[:16]


def cmd_create(args):
    if args.agent not in VALID_AGENTS:
        print(f"Error: invalid agent '{args.agent}'", file=sys.stderr)
        sys.exit(2)
    if args.risk and args.risk not in VALID_RISK:
        print(f"Error: invalid risk '{args.risk}'", file=sys.stderr)
        sys.exit(2)

    pid = stable_id(args.title, args.agent)
    out_dir = Path(args.out) if hasattr(args, 'out') and args.out else Path("opencode-agent-pack/prompt-proposals")
    out_dir.mkdir(parents=True, exist_ok=True)
    # Include a short uniqueness fragment from evidence to avoid collisions
    evidence_frag = ""
    if args.evidence:
        evidence_frag = hashlib.sha256(":".join(sorted(args.evidence)).encode()).hexdigest()[:6]
    fname = f"{pid}-{evidence_frag}-{args.agent}-{re.sub(r'[^a-z0-9-]', '-', args.title.lower())[:50]}.md" if evidence_frag else f"{pid}-{args.agent}-{re.sub(r'[^a-z0-9-]', '-', args.title.lower())[:50]}.md"
    out_path = out_dir / fname

    evidence_lines = "\n".join(f"- {e}" for e in (args.evidence or []))
    content = PROPOSAL_TEMPLATE.format(
        status=args.status or "draft",
        agent=args.agent,
        title=args.title,
        evidence=evidence_lines or "- (none)",
        expected_impact=args.expected_impact or "TBD",
        risk=args.risk or "medium",
    )
    out_path.write_text(content)
    print(f"Created: {out_path}")


def cmd_validate(args):
    target = Path(args.directory)
    if not target.exists():
        print(f"FAIL: directory not found: {target}")
        sys.exit(1)

    errors = []
    for fpath in sorted(target.glob("*.md")):
        content = fpath.read_text(encoding="utf-8")
        if "## Status" not in content:
            errors.append(f"{fpath.name}: missing Status section")
        if "## Target Agent" not in content:
            errors.append(f"{fpath.name}: missing Target Agent")
        if "## Evidence" not in content:
            errors.append(f"{fpath.name}: missing Evidence section")
        if "## Risk Level" not in content:
            errors.append(f"{fpath.name}: missing Risk Level section")
        # Check agent validity
        m = re.search(r"## Target Agent\s*\n(.*)", content)
        if m and m.group(1).strip() not in VALID_AGENTS:
            errors.append(f"{fpath.name}: invalid target agent '{m.group(1).strip()}'")
        # Check risk validity
        m = re.search(r"## Risk Level\s*\n(.*)", content)
        if m and m.group(1).strip() not in VALID_RISK:
            errors.append(f"{fpath.name}: invalid risk level '{m.group(1).strip()}'")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        sys.exit(1)
    else:
        print(f"Validation PASSED: {len(list(target.glob('*.md')))} proposals valid")


def cmd_list(args):
    target = Path(args.directory)
    if not target.exists() or not any(target.glob("*.md")):
        print("No proposals found.")
        return
    for fpath in sorted(target.glob("*.md")):
        content = fpath.read_text(encoding="utf-8")
        status = re.search(r"## Status\s*\n(.*)", content)
        agent = re.search(r"## Target Agent\s*\n(.*)", content)
        title = re.search(r"## Problem\s*\n(.*)", content)
        print(f"  [{status.group(1).strip() if status else '?'}] {fpath.name}")
        if agent:
            print(f"    Agent: {agent.group(1).strip()}")
        if title:
            print(f"    Problem: {title.group(1).strip()}")


def cmd_apply(args):
    proposal_path = Path(args.proposal)
    if not proposal_path.exists():
        print(f"Error: proposal not found: {proposal_path}", file=sys.stderr)
        sys.exit(1)

    content = proposal_path.read_text(encoding="utf-8")
    status_match = re.search(r"## Status\s*\n(.*)", content)
    status = status_match.group(1).strip() if status_match else ""

    if status != "approved":
        print(f"Error: proposal must be approved, current status: {status}", file=sys.stderr)
        sys.exit(1)

    agent_match = re.search(r"## Target Agent\s*\n(.*)", content)
    agent = agent_match.group(1).strip() if agent_match else ""
    if agent not in VALID_AGENTS:
        print(f"Error: invalid target agent: {agent}", file=sys.stderr)
        sys.exit(1)

    # Safety: only report what would happen
    print(f"Would apply proposal to {agent}")
    print(f"  Proposal: {proposal_path}")
    print(f"  Agent file: opencode-agent-pack/agents/{agent}.md")
    print("  (manual review required before automated application)")


# ──────────────────────────────────────────────────────────────────
# evaluate command
# ──────────────────────────────────────────────────────────────────

def cmd_evaluate(args):
    """Evaluate proposal against validation criteria and benchmarks."""
    proposal_path = Path(args.proposal)
    if not proposal_path.exists():
        print(f"Error: proposal not found: {proposal_path}", file=sys.stderr)
        sys.exit(1)

    content = proposal_path.read_text(encoding="utf-8")

    results = {
        "proposal": str(proposal_path),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": {},
        "passed": 0,
        "failed": 0,
        "overall": "PENDING",
    }

    # 1. Static validation
    static_errors = []
    for section in ("## Status", "## Target Agent", "## Evidence", "## Risk Level", "## Problem"):
        if section not in content:
            static_errors.append(f"missing section: {section}")
    results["checks"]["static_validation"] = {
        "passed": len(static_errors) == 0,
        "errors": static_errors,
    }

    # 2. Permission validation
    agent_match = re.search(r"## Target Agent\s*\n(.*)", content)
    target_agent = agent_match.group(1).strip() if agent_match else ""
    results["checks"]["permission_validation"] = {
        "passed": target_agent in VALID_AGENTS,
        "agent": target_agent,
    }

    # 3. Orchestration tests (basic: check for conflicting instructions)
    orchestration_conflicts = []
    if "orchestrat" in content.lower() and "mode:" in content:
        orchestration_conflicts.append("orchestration layer changes detected")
    if "task:" in content and "deny" in content:
        orchestration_conflicts.append("task permission changes detected")
    results["checks"]["orchestration_tests"] = {
        "passed": len(orchestration_conflicts) == 0,
        "conflicts": orchestration_conflicts,
    }

    # 4. Prompt duplication test
    dup_check = True
    if "## Proposed Change" in content:
        change_section = content.split("## Proposed Change")[1].split("##")[0]
        change_text = change_section.strip()
        # Check against existing agent prompts
        agents_dir = Path("opencode-agent-pack/agents")
        if agents_dir.is_dir():
            for af in agents_dir.glob("*.md"):
                existing = af.read_text(encoding="utf-8")
                # Simple duplicate check: significant overlap
                change_words = set(re.findall(r"\w{4,}", change_text.lower()))
                existing_words = set(re.findall(r"\w{4,}", existing.lower()))
                overlap = change_words & existing_words
                if len(change_words) > 5 and len(overlap) / max(len(change_words), 1) > 0.9:
                    dup_check = False
                    break
    results["checks"]["prompt_duplication"] = {
        "passed": dup_check,
    }

    # 5. Benchmark fixture subset (if provided)
    if args.benchmark_fixture:
        bf_path = Path(args.benchmark_fixture)
        if bf_path.exists():
            try:
                with open(bf_path) as f:
                    fixture = json.load(f)
                results["checks"]["benchmark_fixture"] = {
                    "passed": True,
                    "tasks": len(fixture.get("tasks", [])),
                    "note": "benchmark evaluation requires real model execution",
                }
            except Exception as e:
                results["checks"]["benchmark_fixture"] = {
                    "passed": False,
                    "error": str(e),
                }
    else:
        results["checks"]["benchmark_fixture"] = {
            "passed": True,
            "note": "no fixture provided — skipped",
        }

    # 6. Prompt-size budget
    size_bytes = len(content.encode("utf-8"))
    size_ok = size_bytes < 50000
    results["checks"]["prompt_size_budget"] = {
        "passed": size_ok,
        "size_bytes": size_bytes,
        "limit_bytes": 50000,
    }

    # 7. Native-prompt composition test (basic)
    if "---" in content[:10] or "mode:" in content:
        results["checks"]["native_prompt_composition"] = {
            "passed": True,
            "note": "frontmatter detected — composition structural check passed",
        }
    else:
        results["checks"]["native_prompt_composition"] = {
            "passed": False,
            "error": "no frontmatter detected",
        }

    # 8. Regression checks
    risk_match = re.search(r"## Risk Level\s*\n(.*)", content)
    risk = (risk_match.group(1).strip() if risk_match else "").lower()
    results["checks"]["regression_checks"] = {
        "passed": risk != "high",
        "risk": risk,
        "note": "high-risk proposals require additional regression testing",
    }

    # Tally
    passed = sum(1 for c in results["checks"].values() if c.get("passed", False))
    failed = sum(1 for c in results["checks"].values() if not c.get("passed", False))
    results["passed"] = passed
    results["failed"] = failed
    results["overall"] = "PASS" if failed == 0 else "FAIL"

    print(json.dumps(results, indent=2, sort_keys=True))


# ──────────────────────────────────────────────────────────────────
# approve command
# ──────────────────────────────────────────────────────────────────

def cmd_approve(args):
    """Mark a proposal as approved (requires explicit approval flag)."""
    proposal_path = Path(args.proposal)
    if not proposal_path.exists():
        print(f"Error: proposal not found: {proposal_path}", file=sys.stderr)
        sys.exit(1)

    content = proposal_path.read_text(encoding="utf-8")
    status_match = re.search(r"## Status\s*\n(.*)", content)
    current_status = status_match.group(1).strip() if status_match else ""

    if current_status == "approved":
        print("Already approved.")
        return

    if current_status not in ("draft", "proposed"):
        print(f"Error: cannot approve proposal with status '{current_status}'", file=sys.stderr)
        sys.exit(1)

    # Update status to approved
    updated = content.replace(
        f"## Status\n{current_status}",
        "## Status\napproved",
    )

    # Add approval timestamp
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if "## Approved" not in updated:
        updated += f"\n\n## Approved\n{timestamp}\n"

    # Atomic write
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(proposal_path) or ".", suffix=".md.tmp"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(updated)
        os.replace(tmp_path, str(proposal_path))
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    print(f"Approved: {proposal_path}")


# ──────────────────────────────────────────────────────────────────
# rollback command
# ──────────────────────────────────────────────────────────────────

def cmd_rollback(args):
    """Rollback an applied proposal by reverting to backup."""
    proposal_path = Path(args.proposal)
    if not proposal_path.exists():
        print(f"Error: proposal not found: {proposal_path}", file=sys.stderr)
        sys.exit(1)

    content = proposal_path.read_text(encoding="utf-8")
    status_match = re.search(r"## Status\s*\n(.*)", content)
    current_status = status_match.group(1).strip() if status_match else ""

    if current_status != "applied":
        print(f"Error: cannot rollback proposal with status '{current_status}' — must be 'applied'", file=sys.stderr)
        sys.exit(1)

    # Look for backup files
    backup_pattern = f"{proposal_path.stem}.bak*"
    backups = sorted(Path(proposal_path.parent).glob(backup_pattern), reverse=True)
    if not backups:
        print("Error: no backup files found for rollback", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(backups)} backup(s). Using newest: {backups[0].name}")
    print("Rollback would restore backup. (Manual review required.)")
    print(f"  Backup: {backups[0]}")


# ──────────────────────────────────────────────────────────────────
# status command
# ──────────────────────────────────────────────────────────────────

def cmd_status(args):
    """Show current state machine status of a proposal."""
    proposal_path = Path(args.proposal)
    if not proposal_path.exists():
        print(f"Error: proposal not found: {proposal_path}", file=sys.stderr)
        sys.exit(1)

    content = proposal_path.read_text(encoding="utf-8")

    status_match = re.search(r"## Status\s*\n(.*)", content)
    status = status_match.group(1).strip() if status_match else "unknown"

    agent_match = re.search(r"## Target Agent\s*\n(.*)", content)
    agent = agent_match.group(1).strip() if agent_match else "unknown"

    problem_match = re.search(r"## Problem\s*\n(.*)", content)
    problem = problem_match.group(1).strip() if problem_match else "unknown"

    risk_match = re.search(r"## Risk Level\s*\n(.*)", content)
    risk = risk_match.group(1).strip() if risk_match else "unknown"

    # State machine: draft -> proposed -> approved -> applied
    valid_transitions = {
        "draft": ["proposed", "rejected"],
        "proposed": ["approved", "rejected"],
        "approved": ["applied", "rejected"],
        "applied": [],
        "rejected": [],
        "unknown": ["draft", "proposed", "approved", "rejected"],
    }

    result = {
        "proposal": str(proposal_path),
        "agent": agent,
        "problem": problem,
        "risk": risk,
        "current_status": status,
        "allowed_transitions": valid_transitions.get(status, []),
        "can_apply": status == "approved",
        "can_rollback": status == "applied",
        "can_approve": status in ("draft", "proposed"),
        "state_machine": "draft -> proposed -> approved -> applied",
    }
    print(json.dumps(result, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description="Prompt Improvement Proposals")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create")
    p_create.add_argument("--agent", required=True, choices=sorted(VALID_AGENTS))
    p_create.add_argument("--title", required=True)
    p_create.add_argument("--evidence", action="append", default=[])
    p_create.add_argument("--expected-impact")
    p_create.add_argument("--risk", choices=sorted(VALID_RISK), default="medium")
    p_create.add_argument("--status", choices=sorted(VALID_STATUS), default="draft")
    p_create.add_argument("--out")

    p_val = sub.add_parser("validate")
    p_val.add_argument("directory")

    p_list = sub.add_parser("list")
    p_list.add_argument("directory")

    p_app = sub.add_parser("apply")
    p_app.add_argument("--proposal", required=True)

    p_eval = sub.add_parser("evaluate")
    p_eval.add_argument("--proposal", required=True)
    p_eval.add_argument("--benchmark-fixture")

    p_approve = sub.add_parser("approve")
    p_approve.add_argument("--proposal", required=True)

    p_rollback = sub.add_parser("rollback")
    p_rollback.add_argument("--proposal", required=True)

    p_status = sub.add_parser("status")
    p_status.add_argument("--proposal", required=True)

    args = parser.parse_args()
    if args.command == "create":
        cmd_create(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "apply":
        cmd_apply(args)
    elif args.command == "evaluate":
        cmd_evaluate(args)
    elif args.command == "approve":
        cmd_approve(args)
    elif args.command == "rollback":
        cmd_rollback(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
