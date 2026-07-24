#!/usr/bin/env python3
"""
Strategy Selector — deterministic rule-based strategy selection for Heidi.

Commands:
  select --task <t> [--context <f>]   Select a strategy for the task
  fast-path-check --task <t> [--context <f>]  Check if fast path applies
  validate <file>                     Validate strategies config file
"""

import argparse
import json
import sys
from pathlib import Path

STRATEGY_RULES = [
    {
        "strategy": "prompt_improvement_proposal",
        "keywords": ["prompt", "agent instruction", "agent behavior", "improve prompt", "rewrite agent"],
        "context_signals": [],
        "priority": 10,
    },
    {
        "strategy": "audit_only",
        "keywords": ["audit", "code review", "security review", "review"],
        "context_signals": [],
        "priority": 10,
    },
    {
        "strategy": "debugger_root_cause",
        "keywords": ["ci", "failing", "broken build", "bug", "regression", "test failure", "401", "403", "500", "502", "crash"],
        "context_signals": ["test_files"],
        "priority": 9,
    },
    {
        "strategy": "frontend_backend_parallel",
        "keywords": ["frontend", "backend", "ui", "api", "database", "migration"],
        "context_signals": [],
        "priority": 8,
        "requires_both_domains": True,
    },
    {
        "strategy": "explore_then_direct",
        "keywords": ["new", "unfamiliar", "explore", "investigate"],
        "context_signals": [],
        "priority": 7,
        "description": "Use native explore agent when available, then direct execution",
    },
    {
        "strategy": "scout_then_execute",
        "keywords": ["roadmap", "plan", "feature", "architecture", "design", "spec"],
        "context_signals": [],
        "priority": 7,
    },
    {
        "strategy": "planner_gate",
        "keywords": ["large feature", "major change", "refactor", "migration plan"],
        "context_signals": [],
        "priority": 5,
    },
    {
        "strategy": "audit_after_change",
        "keywords": ["security", "auth", "permission", "deployment", "production"],
        "context_signals": [],
        "priority": 6,
        "description": "Run audit after making changes",
    },
    {
        "strategy": "fast_direct",
        "keywords": [],
        "context_signals": [],
        "priority": 0,
        "description": "Fast path for trivial single-file changes",
    },
    {
        "strategy": "direct_single_agent",
        "keywords": [],
        "context_signals": [],
        "priority": 0,
        "fallback": True,
    },
]

STRATEGY_AGENTS = {
    "prompt_improvement_proposal": ["auditor", "heidi"],
    "audit_only": ["auditor"],
    "debugger_root_cause": ["debugger", "auditor"],
    "frontend_backend_parallel": ["frontend", "backend"],
    "scout_then_execute": ["scout"],
    "explore_then_direct": ["scout", "heidi"],
    "planner_gate": ["planner"],
    "audit_after_change": ["heidi", "auditor"],
    "fast_direct": ["heidi"],
    "direct_single_agent": ["heidi"],
}

STRATEGY_PARALLEL = {
    "frontend_backend_parallel": True,
}

STRATEGY_REQUIRES_SCOUT = {
    "scout_then_execute": True,
    "explore_then_direct": True,
}

STRATEGY_REQUIRES_AUDITOR = {
    "audit_only": True,
    "audit_after_change": True,
    "prompt_improvement_proposal": True,
}

STRATEGY_COMPLEXITY = {
    "fast_direct": "small",
    "direct_single_agent": "small",
    "explore_then_direct": "small",
    "scout_then_execute": "medium",
    "debugger_root_cause": "medium",
    "audit_after_change": "medium",
    "frontend_backend_parallel": "large",
    "planner_gate": "large",
    "prompt_improvement_proposal": "large",
    "audit_only": "medium",
}

STRATEGY_RISK = {
    "fast_direct": "low",
    "direct_single_agent": "low",
    "explore_then_direct": "low",
    "scout_then_execute": "medium",
    "debugger_root_cause": "medium",
    "audit_after_change": "medium",
    "frontend_backend_parallel": "medium",
    "planner_gate": "high",
    "prompt_improvement_proposal": "high",
    "audit_only": "critical",
}


def has_both_domains(task_lower):
    frontend_words = {"frontend", "ui", "component", "react", "tailwind", "css", "layout", "page", "form"}
    backend_words = {"backend", "api", "database", "prisma", "migration", "server", "endpoint", "auth"}
    has_fe = bool(frontend_words & set(task_lower.split()))
    has_be = bool(backend_words & set(task_lower.split()))
    return has_fe and has_be


def cmd_select(args):
    task_lower = args.task.lower()

    best_strategy = None
    best_priority = -1
    best_reason = "No specific strategy matched."

    for rule in STRATEGY_RULES:
        matched = False
        reasons = []

        # Keyword matching
        if rule.get("keywords"):
            matched_kw = [kw for kw in rule["keywords"] if kw.lower() in task_lower]
            if matched_kw:
                matched = True
                reasons.append(f"keywords: {', '.join(matched_kw)}")

        # Context signals
        if args.context:
            try:
                with open(args.context) as f:
                    ctx = json.load(f)
                signals = ctx.get("summary", {})
                if "test_files" in rule.get("context_signals", []) and signals.get("test_files"):
                    matched = True
                    reasons.append("has test files")
            except Exception:
                pass

        # Domain requirement
        if rule.get("requires_both_domains") and not has_both_domains(task_lower):
            matched = False

        if matched and rule["priority"] >= best_priority:
            best_strategy = rule["strategy"]
            best_priority = rule["priority"]
            best_reason = "; ".join(reasons) if reasons else "rule matched by default"

    # Fallback to direct_single_agent
    if best_strategy is None:
        best_strategy = "direct_single_agent"
        best_priority = 0
        best_reason = "Fallback: no strategy matched"

    # Apply fast path check
    fast_path = check_fast_path(task_lower, args.context)
    if fast_path["applies"] and best_priority <= 5:
        # Fast path only overrides low-priority strategies
        best_strategy = "fast_direct"
        best_reason = f"Fast path: {fast_path['reason']}"

    agents = STRATEGY_AGENTS.get(best_strategy, ["heidi"])
    parallel = STRATEGY_PARALLEL.get(best_strategy, False)
    complexity = STRATEGY_COMPLEXITY.get(best_strategy, "medium")
    risk = STRATEGY_RISK.get(best_strategy, "medium")
    requires_scout = STRATEGY_REQUIRES_SCOUT.get(best_strategy, False)
    requires_auditor = STRATEGY_REQUIRES_AUDITOR.get(best_strategy, False)

    # Confidence heuristic
    if best_priority >= 9:
        confidence = "high"
    elif best_priority >= 5:
        confidence = "medium"
    else:
        confidence = "low"

    result = {
        "strategy": best_strategy,
        "complexity": complexity,
        "risk": risk,
        "confidence": confidence,
        "agents": agents,
        "parallelizable": parallel,
        "requires_scout": requires_scout,
        "requires_auditor": requires_auditor,
        "fast_path": best_strategy == "fast_direct",
        "reason": best_reason,
        "verification_gates": _verification_gates(best_strategy),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


def _verification_gates(strategy):
    """Return verification gates appropriate for the strategy."""
    gates = {
        "fast_direct": ["targeted test"],
        "direct_single_agent": ["targeted test", "lint/typecheck"],
        "explore_then_direct": ["scout report", "targeted test"],
        "scout_then_execute": ["scout report", "plan review", "targeted test"],
        "debugger_root_cause": ["root cause confirmed", "regression test"],
        "frontend_backend_parallel": ["integration test", "e2e smoke"],
        "planner_gate": ["plan approved", "implementation review"],
        "audit_only": ["audit report", "no unauthorized changes"],
        "audit_after_change": ["change audit", "security review", "regression test"],
        "prompt_improvement_proposal": ["proposal validated", "benchmark comparison"],
    }
    return gates.get(strategy, ["targeted test", "lint/typecheck"])


def check_fast_path(task, context_path=None):
    """Check whether fast_direct strategy applies.

    Fast path rules: ALL must be true:
      - One clear objective (single sentence-ish task)
      - Low risk (no auth/permission/deployment keywords)
      - Likely 1-2 files (no "refactor", "architecture", "migration")
      - No database/auth/deployment changes
      - No architecture decision
      - No failing CI reference
      - No user-requested audit
      - No conflicting ownership
    """
    task_lower = task.lower()

    # High-risk keywords that disqualify fast path
    disqualifiers = {
        "auth": "auth-related change",
        "authentication": "authentication change",
        "permission": "permission change",
        "database": "database change",
        "migration": "schema migration",
        "deployment": "deployment-related",
        "deploy": "deployment-related",
        "production": "production change",
        "architecture": "architecture decision",
        "architect": "architecture decision",
        "refactor": "multi-file refactor",
        "rewrite": "multi-file rewrite",
        "ci": "CI change",
        "pipeline": "pipeline change",
        "audit": "audit requested",
        "review": "review requested",
        "security": "security change",
        "encrypt": "security change",
        "decrypt": "security change",
        "infrastructure": "infrastructure change",
        "config": "config change",
        "plugin": "plugin system change",
        "orchestrat": "orchestration change",
    }

    reasons = []
    for kw, reason in disqualifiers.items():
        if kw in task_lower:
            reasons.append(reason)

    if reasons:
        return {"applies": False, "reason": "; ".join(reasons)}

    # Context-based checks
    if context_path:
        try:
            with open(context_path) as f:
                ctx = json.load(f)
            summary = ctx.get("summary", {})
            # If > 20 test files, might be complex
            if len(summary.get("test_files", [])) > 20:
                return {"applies": False, "reason": "many test files (>20) indicate complexity"}
            # If > 50 config files, likely not fast
            if len(summary.get("config_files", [])) > 50:
                return {"applies": False, "reason": "many config files indicate complexity"}
        except Exception:
            pass

    return {"applies": True, "reason": "one clear objective, low risk, likely 1-2 files"}


def cmd_fast_path_check(args):
    """Check if fast_path applies for a given task."""
    result = check_fast_path(args.task, args.context)
    result["task"] = args.task[:100]
    print(json.dumps(result, indent=2, sort_keys=True))


def cmd_validate(args):
    path = Path(args.file)
    if not path.exists():
        print(f"FAIL: file not found: {path}")
        sys.exit(1)
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            print("FAIL: strategies file must be a JSON object")
            sys.exit(1)
        print(f"Validation PASSED: {path}")
    except json.JSONDecodeError as e:
        print(f"FAIL: invalid JSON: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Strategy Selector")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sel = sub.add_parser("select", help="Select strategy")
    p_sel.add_argument("--task", required=True)
    p_sel.add_argument("--context")

    p_fast = sub.add_parser("fast-path-check", help="Check if fast path applies")
    p_fast.add_argument("--task", required=True)
    p_fast.add_argument("--context")

    p_val = sub.add_parser("validate", help="Validate strategies file")
    p_val.add_argument("file")

    args = parser.parse_args()
    if args.command == "select":
        cmd_select(args)
    elif args.command == "fast-path-check":
        cmd_fast_path_check(args)
    elif args.command == "validate":
        cmd_validate(args)


if __name__ == "__main__":
    main()
