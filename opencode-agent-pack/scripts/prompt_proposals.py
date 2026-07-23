#!/usr/bin/env python3
"""
Verified Prompt Improvement Proposals — safe prompt evolution system.

Commands:
  create --agent <a> --title <t> --evidence <e> --expected-impact <i>
         Create a prompt improvement proposal
  validate <dir>              Validate all proposals in a directory
  list <dir>                  List proposals
  apply --proposal <f>        Apply an approved proposal (requires safety checks)
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

    args = parser.parse_args()
    if args.command == "create":
        cmd_create(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "apply":
        cmd_apply(args)


if __name__ == "__main__":
    main()
