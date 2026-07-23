#!/usr/bin/env python3
"""
Strategy Selector — deterministic rule-based strategy selection for Heidi.

Commands:
  select --task <t> [--context <f>]   Select a strategy for the task
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
        "strategy": "scout_then_execute",
        "keywords": ["new", "unfamiliar", "explore", "investigate"],
        "context_signals": [],
        "priority": 7,
    },
    {
        "strategy": "planner_then_execute",
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
        "strategy": "direct_single_agent",
        "keywords": [],
        "context_signals": [],
        "priority": 0,
    },
]

STRATEGY_AGENTS = {
    "prompt_improvement_proposal": ["auditor", "heidi"],
    "audit_only": ["auditor"],
    "debugger_root_cause": ["debugger", "auditor"],
    "frontend_backend_parallel": ["frontend", "backend"],
    "scout_then_execute": ["scout"],
    "planner_then_execute": ["planner"],
    "planner_gate": ["planner"],
    "direct_single_agent": ["heidi"],
}

STRATEGY_PARALLEL = {
    "frontend_backend_parallel": True,
}


def has_both_domains(task_lower):
    frontend_words = {"frontend", "ui", "component", "react", "tailwind", "css", "layout", "page", "form"}
    backend_words = {"backend", "api", "database", "prisma", "migration", "server", "endpoint", "auth"}
    has_fe = bool(frontend_words & set(task_lower.split()))
    has_be = bool(backend_words & set(task_lower.split()))
    return has_fe and has_be


def cmd_select(args):
    task_lower = args.task.lower()

    best_strategy = "direct_single_agent"
    best_priority = -1
    best_reason = "No specific strategy matched. Defaulting to direct single agent."

    for rule in STRATEGY_RULES:
        matched = False
        reasons = []

        # Keyword matching
        if rule["keywords"]:
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

        if matched and rule["priority"] > best_priority:
            best_strategy = rule["strategy"]
            best_priority = rule["priority"]
            best_reason = "; ".join(reasons)

    agents = STRATEGY_AGENTS.get(best_strategy, ["heidi"])
    parallel = STRATEGY_PARALLEL.get(best_strategy, False)

    result = {
        "strategy": best_strategy,
        "confidence": "high" if best_priority >= 7 else "medium" if best_priority >= 4 else "low",
        "reason": best_reason,
        "agents": agents,
        "parallelizable": parallel,
        "requires_human_approval": best_strategy in ("audit_only", "prompt_improvement_proposal"),
        "verification_gates": ["targeted test", "agent validation"],
    }
    print(json.dumps(result, indent=2))


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

    p_val = sub.add_parser("validate", help="Validate strategies file")
    p_val.add_argument("file")

    args = parser.parse_args()
    if args.command == "select":
        cmd_select(args)
    elif args.command == "validate":
        cmd_validate(args)


if __name__ == "__main__":
    main()
