#!/usr/bin/env python3
"""
Delegation Handoff — compact structured handoff for subagent delegation.

Replaces full-context delegation with a compact handoff containing only:
- Task objective
- Assigned agent
- Owned files or directories
- Locked/shared files
- Relevant constraints
- Minimal evidence
- Acceptance checks
- Previous call reference (for follow-ups)
- Remaining token and call budget

The handoff is capped at a configurable token limit (default ~1500 tokens,
strict maximum 4000 tokens).
"""

import hashlib
import json
import os
from pathlib import Path

DEFAULT_DELEGATION_CONTEXT_LIMIT = 1500
MAX_DELEGATION_CONTEXT_LIMIT = 4000


def build_handoff(task_objective, agent, owned_files=None, shared_files=None,
                  constraints=None, evidence=None, acceptance_checks=None,
                  previous_call_ref=None, remaining_budget=None,
                  context_limit=DEFAULT_DELEGATION_CONTEXT_LIMIT):
    """Build a compact structured handoff for subagent delegation.

    Args:
        task_objective: The specific task this agent should accomplish.
        agent: The agent name (scout, frontend, backend, debugger, auditor, planner).
        owned_files: List of files/dirs this agent owns.
        shared_files: List of files that are shared/locked.
        constraints: List of relevant constraints from project rules.
        evidence: Minimal evidence needed for the task.
        acceptance_checks: List of acceptance criteria.
        previous_call_ref: Reference to previous call (for follow-ups).
        remaining_budget: Dict with remaining token/call budget.
        context_limit: Maximum tokens for the handoff payload.

    Returns:
        A compact handoff dict that fits within the token limit.
    """
    # Enforce limits
    context_limit = min(context_limit, MAX_DELEGATION_CONTEXT_LIMIT)

    handoff = {
        "task_objective": task_objective,
        "agent": agent,
    }

    if owned_files:
        handoff["owned_files"] = _truncate_list(owned_files, context_limit, "owned_files")

    if shared_files:
        handoff["shared_files"] = _truncate_list(shared_files, context_limit, "shared_files")

    if constraints:
        handoff["constraints"] = _truncate_list(constraints, context_limit, "constraints")

    if evidence:
        handoff["evidence"] = _truncate_list(evidence, context_limit, "evidence")

    if acceptance_checks:
        handoff["acceptance_checks"] = _truncate_list(acceptance_checks, context_limit, "acceptance_checks")

    if previous_call_ref:
        handoff["previous_call_ref"] = previous_call_ref

    if remaining_budget:
        handoff["remaining_budget"] = remaining_budget

    # Exclude: conversation history, full Scout reports, unrelated repo summaries,
    # full terminal logs, unchanged file contents, reports already in task artifacts.

    # Verify size
    serialized = json.dumps(handoff, sort_keys=True)
    estimated_tokens = _estimate_tokens(serialized)

    if estimated_tokens > context_limit:
        # Truncate evidence and constraints further
        handoff = _aggressive_truncate(handoff, context_limit)

    return handoff


def build_followup_handoff(previous_handoff, new_failure, changed_files=None,
                          remaining_issue=None, required_correction=None,
                          remaining_budget=None):
    """Build a delta-only handoff for follow-up calls.

    Only includes:
    - New failure
    - Changed files
    - Remaining issue
    - Required correction
    - Previous call reference
    - Remaining budget
    """
    handoff = {
        "type": "followup",
        "previous_call_ref": previous_handoff.get("task_objective", ""),
        "new_failure": new_failure,
    }

    if changed_files:
        handoff["changed_files"] = changed_files

    if remaining_issue:
        handoff["remaining_issue"] = remaining_issue

    if required_correction:
        handoff["required_correction"] = required_correction

    if remaining_budget:
        handoff["remaining_budget"] = remaining_budget

    return handoff


def _truncate_list(items, budget, field_name):
    """Truncate a list of items to fit within the remaining budget."""
    if not items:
        return items
    result = []
    used = sum(len(json.dumps(item)) for item in items[:1])  # rough estimate
    for item in items:
        item_size = len(json.dumps(item))
        if used + item_size > budget * 0.3:  # reserve 30% for other fields
            break
        result.append(item)
        used += item_size
    return result


def _aggressive_truncate(handoff, limit):
    """Aggressively truncate handoff to fit within limit."""
    # Keep only essential fields, truncate long values
    essential = {
        "task_objective": handoff.get("task_objective", "")[:200],
        "agent": handoff.get("agent", ""),
    }
    if handoff.get("owned_files"):
        essential["owned_files"] = handoff["owned_files"][:3]
    if handoff.get("acceptance_checks"):
        essential["acceptance_checks"] = handoff["acceptance_checks"][:3]
    if handoff.get("previous_call_ref"):
        essential["previous_call_ref"] = handoff["previous_call_ref"]
    if handoff.get("remaining_budget"):
        essential["remaining_budget"] = handoff["remaining_budget"]
    return essential


def _estimate_tokens(text):
    """Rough token estimate from text."""
    return max(1, int(len(text) / 4.0))


def validate_handoff_size(handoff, limit=DEFAULT_DELEGATION_CONTEXT_LIMIT):
    """Validate that a handoff fits within the token limit.

    Returns (valid: bool, actual_tokens: int, limit: int).
    """
    serialized = json.dumps(handoff, sort_keys=True)
    tokens = _estimate_tokens(serialized)
    return tokens <= limit, tokens, limit


def fingerprint_handoff(handoff):
    """Create a stable fingerprint for a handoff."""
    key_parts = [
        handoff.get("task_objective", ""),
        handoff.get("agent", ""),
        json.dumps(handoff.get("owned_files", []), sort_keys=True),
        json.dumps(handoff.get("shared_files", []), sort_keys=True),
    ]
    raw = "|".join(key_parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── CLI ────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Delegation Handoff Builder")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Build a compact handoff")
    p_build.add_argument("--objective", required=True)
    p_build.add_argument("--agent", required=True)
    p_build.add_argument("--owned-files", nargs="*", default=[])
    p_build.add_argument("--shared-files", nargs="*", default=[])
    p_build.add_argument("--constraints", nargs="*", default=[])
    p_build.add_argument("--evidence", nargs="*", default=[])
    p_build.add_argument("--acceptance-checks", nargs="*", default=[])
    p_build.add_argument("--previous-call-ref", default=None)
    p_build.add_argument("--remaining-budget", default=None)
    p_build.add_argument("--context-limit", type=int, default=DEFAULT_DELEGATION_CONTEXT_LIMIT)

    p_followup = sub.add_parser("followup", help="Build a follow-up handoff")
    p_followup.add_argument("--previous", required=True, help="JSON of previous handoff")
    p_followup.add_argument("--new-failure", required=True)
    p_followup.add_argument("--changed-files", nargs="*", default=[])
    p_followup.add_argument("--remaining-issue", default=None)
    p_followup.add_argument("--required-correction", default=None)
    p_followup.add_argument("--remaining-budget", default=None)

    p_validate = sub.add_parser("validate", help="Validate handoff size")
    p_validate.add_argument("--handoff", required=True, help="JSON handoff")
    p_validate.add_argument("--limit", type=int, default=DEFAULT_DELEGATION_CONTEXT_LIMIT)

    args = parser.parse_args()

    if args.command == "build":
        remaining = json.loads(args.remaining_budget) if args.remaining_budget else None
        handoff = build_handoff(
            task_objective=args.objective,
            agent=args.agent,
            owned_files=args.owned_files or None,
            shared_files=args.shared_files or None,
            constraints=args.constraints or None,
            evidence=args.evidence or None,
            acceptance_checks=args.acceptance_checks or None,
            previous_call_ref=args.previous_call_ref,
            remaining_budget=remaining,
            context_limit=args.context_limit,
        )
        valid, tokens, limit = validate_handoff_size(handoff, args.context_limit)
        handoff["_estimated_tokens"] = tokens
        handoff["_within_limit"] = valid
        print(json.dumps(handoff, indent=2, sort_keys=True))

    elif args.command == "followup":
        previous = json.loads(args.previous)
        remaining = json.loads(args.remaining_budget) if args.remaining_budget else None
        handoff = build_followup_handoff(
            previous_handoff=previous,
            new_failure=args.new_failure,
            changed_files=args.changed_files or None,
            remaining_issue=args.remaining_issue,
            required_correction=args.required_correction,
            remaining_budget=remaining,
        )
        print(json.dumps(handoff, indent=2, sort_keys=True))

    elif args.command == "validate":
        handoff = json.loads(args.handoff)
        valid, tokens, limit = validate_handoff_size(handoff, args.limit)
        result = {"valid": valid, "estimated_tokens": tokens, "limit": limit}
        print(json.dumps(result, indent=2, sort_keys=True))
        if not valid:
            import sys
            sys.exit(1)


if __name__ == "__main__":
    main()