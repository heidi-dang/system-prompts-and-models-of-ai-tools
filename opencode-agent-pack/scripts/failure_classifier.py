#!/usr/bin/env python3
"""
Failure Classifier — classify failures into known categories.

Failure categories:
  implementation, test_expectation, dependency, environment, permission,
  context, configuration, tool_invocation, external_service, unknown

Commands:
  classify --type <t> --evidence <e>   Classify a failure
  policy --type <t>                    Show retry policy for a failure type
"""

import argparse
import json
import sys

# ──────────────────────────────────────────────────────────────────
# Failure category definitions
# ──────────────────────────────────────────────────────────────────

FAILURE_CATEGORIES = {
    "implementation": {
        "description": "Code logic error, bug in implementation",
        "evidence_requirements": ["stack trace", "test failure output", "code diff context"],
        "retry_allowance": 3,
        "permitted_next_strategy": ["debugger_root_cause", "direct_single_agent"],
        "escalation_condition": "retries exhausted or complexity > medium",
        "user_action_checkpoint": "after 3 retries, ask user to clarify requirements",
    },
    "test_expectation": {
        "description": "Test expectation mismatch, not a code bug",
        "evidence_requirements": ["test file diff", "expected vs actual output"],
        "retry_allowance": 2,
        "permitted_next_strategy": ["direct_single_agent", "scout_then_execute"],
        "escalation_condition": "test expectation fundamentally conflicts with spec",
        "user_action_checkpoint": "confirm test expectation change with user before modifying tests",
    },
    "dependency": {
        "description": "Missing or broken dependency",
        "evidence_requirements": ["install error", "import/module error", "dependency tree diff"],
        "retry_allowance": 3,
        "permitted_next_strategy": ["direct_single_agent", "explore_then_direct"],
        "escalation_condition": "native dependency or system package required",
        "user_action_checkpoint": "prompt user to install system dependency manually",
    },
    "environment": {
        "description": "Environment mismatch (OS, Python version, PATH, etc.)",
        "evidence_requirements": ["env diff", "version mismatch output"],
        "retry_allowance": 1,
        "permitted_next_strategy": ["direct_single_agent"],
        "escalation_condition": "always escalate for env issues",
        "user_action_checkpoint": "report environment mismatch to user immediately",
    },
    "permission": {
        "description": "Permission denied (file, network, auth)",
        "evidence_requirements": ["permission error message", "auth error response"],
        "retry_allowance": 1,
        "permitted_next_strategy": ["direct_single_agent"],
        "escalation_condition": "always escalate for permission issues",
        "user_action_checkpoint": "request elevated permissions or token refresh from user",
    },
    "context": {
        "description": "Insufficient context / context index stale",
        "evidence_requirements": ["context search result", "missing file references"],
        "retry_allowance": 2,
        "permitted_next_strategy": ["scout_then_execute", "explore_then_direct"],
        "escalation_condition": "context index is stale and cannot be refreshed automatically",
        "user_action_checkpoint": "ask user to provide additional context or run context refresh",
    },
    "configuration": {
        "description": "Configuration error (misconfigured agent, bad JSON)",
        "evidence_requirements": ["config file diff", "parse error output"],
        "retry_allowance": 2,
        "permitted_next_strategy": ["direct_single_agent", "audit_after_change"],
        "escalation_condition": "config change requires approval",
        "user_action_checkpoint": "show proposed config diff before applying",
    },
    "tool_invocation": {
        "description": "Tool/instrumentation failure (bash command, API tool)",
        "evidence_requirements": ["tool error output", "tool name and args"],
        "retry_allowance": 2,
        "permitted_next_strategy": ["direct_single_agent"],
        "escalation_condition": "same tool fails 2+ times with same args",
        "user_action_checkpoint": "suggest alternative approach to user",
    },
    "external_service": {
        "description": "External service failure (CI, API, database)",
        "evidence_requirements": ["service error response", "timeout message"],
        "retry_allowance": 3,
        "permitted_next_strategy": ["direct_single_agent"],
        "escalation_condition": "service is fully down or rate-limited",
        "user_action_checkpoint": "wait for service recovery or use retry-with-backoff",
    },
    "unknown": {
        "description": "Unclassified failure",
        "evidence_requirements": ["any available error output"],
        "retry_allowance": 1,
        "permitted_next_strategy": ["scout_then_execute"],
        "escalation_condition": "always escalate unknown failures",
        "user_action_checkpoint": "surface full error to user for manual classification",
    },
}


# ──────────────────────────────────────────────────────────────────
# Classification heuristics
# ──────────────────────────────────────────────────────────────────

def classify_failure(failure_type, evidence):
    """Classify a failure based on type hint and evidence text.

    Returns a dict with classification details.
    """
    evidence_lower = (evidence or "").lower()

    # Keyword-based heuristics when type is ambiguous or "unknown"
    if failure_type in ("unknown", None, ""):
        failure_type = _infer_type(evidence_lower)

    category = FAILURE_CATEGORIES.get(failure_type, FAILURE_CATEGORIES["unknown"])
    return {
        "type": failure_type,
        "classification": category,
    }


def _infer_type(evidence_lower):
    """Infer failure type from evidence content."""
    if any(kw in evidence_lower for kw in ("permission denied", "access denied", "eacces", "unauthorized", "forbidden")):
        return "permission"
    if any(kw in evidence_lower for kw in ("module not found", "cannot find module", "import error", "modulenotfound")):
        return "dependency"
    if any(kw in evidence_lower for kw in ("assertionerror", "assert", "expected", "assert_equal", "assertin", "asserttrue")):
        return "test_expectation"
    if any(kw in evidence_lower for kw in ("rate limit", "timeout", "connection refused", "dns", "http 5")):
        return "external_service"
    if any(kw in evidence_lower for kw in ("stack trace", "traceback", "error", "exception", "typeerror", "valueerror", "attributeerror", "keyerror", "syntaxerror")):
        return "implementation"
    if any(kw in evidence_lower for kw in ("config", "json", "yaml", "schema", "validation")):
        return "configuration"
    if any(kw in evidence_lower for kw in ("bash", "tool", "command", "subprocess")):
        return "tool_invocation"
    if any(kw in evidence_lower for kw in ("context", "index", "stale", "fingerprint")):
        return "context"
    if any(kw in evidence_lower for kw in ("environment", "env", "path", "version")):
        return "environment"
    return "unknown"


# ──────────────────────────────────────────────────────────────────
# CLI commands
# ──────────────────────────────────────────────────────────────────

def cmd_classify(args):
    """Classify a failure and print policy + recommendation."""
    result = classify_failure(args.type, args.evidence)
    cat = result["classification"]

    output = {
        "type": result["type"],
        "description": cat["description"],
        "retry_allowance": cat["retry_allowance"],
        "permitted_strategies": cat["permitted_next_strategy"],
        "escalation_condition": cat["escalation_condition"],
        "user_action_checkpoint": cat["user_action_checkpoint"],
    }
    print(json.dumps(output, indent=2, sort_keys=True))


def cmd_policy(args):
    """Show the retry policy for a specific failure type."""
    cat = FAILURE_CATEGORIES.get(args.type)
    if not cat:
        print(f"Error: unknown failure type '{args.type}'", file=sys.stderr)
        print(f"Valid types: {', '.join(sorted(FAILURE_CATEGORIES.keys()))}", file=sys.stderr)
        sys.exit(1)

    print(f"Failure type: {args.type}")
    print(f"Description:    {cat['description']}")
    print(f"Retry allowance: {cat['retry_allowance']}")
    print(f"Next strategies: {', '.join(cat['permitted_next_strategy'])}")
    print(f"Escalates when:  {cat['escalation_condition']}")
    print(f"User checkpoint: {cat['user_action_checkpoint']}")


# ──────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Failure Classifier")
    sub = parser.add_subparsers(dest="command", required=True)

    p_classify = sub.add_parser("classify", help="Classify a failure")
    p_classify.add_argument("--type", help="Failure type hint (or 'unknown')")
    p_classify.add_argument("--evidence", required=True, help="Error text / evidence for classification")

    p_policy = sub.add_parser("policy", help="Show retry policy for a failure type")
    p_policy.add_argument("--type", required=True, help="Failure type")

    args = parser.parse_args()

    if args.command == "classify":
        cmd_classify(args)
    elif args.command == "policy":
        cmd_policy(args)


if __name__ == "__main__":
    main()
