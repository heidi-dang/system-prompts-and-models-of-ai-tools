#!/usr/bin/env python3
"""
Strategy Selector — deterministic normalized classification for Heidi.

Uses exact word/phrase token matching with weighted signals instead of
substring matching. Reports confidence, uncertainty, and fallback reasons.

Commands:
  select --task <t> [--context <f>]   Select a strategy for the task
  fast-path-check --task <t>          Check if fast path applies
  validate <file>                     Validate strategies config file
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# ── Normalized strategy definitions ─────────────────────────────

# Each strategy has: exact phrases (must match word-boundary), weighted signals
# (these add score but don't decide alone), context requirements, and priority.

STRATEGY_DEFS = {
    "audit_only": {
        "priority": 10,
        "exact_phrases": [
            "code review", "security review", "architecture review", "pr review",
            "production readiness review", "regression review", "full audit",
            "audit the", "audit this", "audit our", "audit my", "audit codebase",
        ],
        "single_words": ["audit"],
        "signals": {},
        "agents": ["auditor"],
    },
    "debugger_root_cause": {
        "priority": 9,
        "exact_phrases": [
            "failing test", "broken build", "test failure", "production bug",
            "ci failure", "ci failing", "failing ci", "pipeline failure", "build broken",
            "http 401", "http 403", "http 500", "http 502", "segfault",
        ],
        "single_words": ["regression", "crash"],
        "signals": {"test_files": True},
        "agents": ["debugger", "auditor"],
    },
    "frontend_backend_parallel": {
        "priority": 8,
        "exact_phrases": [
            "frontend and backend", "ui and api", "full stack",
            "fullstack", "front end and back end",
        ],
        "single_words": ["frontend", "backend"],
        "signals": {},
        "requires_both_domains": True,
        "agents": ["frontend", "backend"],
    },
    "scout_then_execute": {
        "priority": 7,
        "exact_phrases": [
            "architecture plan", "design spec", "roadmap planning",
            "new repository", "unfamiliar codebase", "project scaffold",
            "project roadmap", "architecture roadmap",
        ],
        "single_words": ["architecture", "design", "roadmap"],
        "signals": {},
        "agents": ["scout"],
    },
    "explore_then_direct": {
        "priority": 6,
        "exact_phrases": [
            "explore the codebase", "investigate the project",
            "find all", "locate the definition",
        ],
        "single_words": ["explore", "investigate"],
        "signals": {},
        "agents": ["scout", "heidi"],
    },
    "audit_after_change": {
        "priority": 6,
        "exact_phrases": [
            "authentication change", "authorization change", "permission change",
            "security fix", "schema migration", "deploy to production",
            "production deploy",
        ],
        "single_words": ["auth", "permission", "migration"],
        "signals": {},
        "agents": ["heidi", "auditor"],
    },
    "planner_gate": {
        "priority": 5,
        "exact_phrases": [
            "major refactor", "large feature", "migration plan", "re-architecture",
        ],
        "single_words": ["refactor", "rewrite"],
        "signals": {},
        "agents": ["planner"],
    },
    "scout_only": {
        "priority": 4,
        "exact_phrases": ["project profile", "stack detection", "directory map"],
        "single_words": [],
        "signals": {},
        "agents": ["scout"],
    },
    "fast_direct": {
        "priority": 1,
        "exact_phrases": [],
        "single_words": [],
        "signals": {},
        "agents": ["heidi"],
        "fallback": False,
    },
    "direct_single_agent": {
        "priority": 0,
        "exact_phrases": [],
        "single_words": [],
        "signals": {},
        "agents": ["heidi"],
        "fallback": True,
    },
}

STRATEGY_COMPLEXITY = {
    "audit_only": "medium",
    "debugger_root_cause": "medium",
    "frontend_backend_parallel": "large",
    "scout_then_execute": "medium",
    "explore_then_direct": "small",
    "audit_after_change": "medium",
    "planner_gate": "large",
    "scout_only": "small",
    "fast_direct": "small",
    "direct_single_agent": "small",
}

# Audit is read-only — not critical risk unless sensitive code is explicitly involved
STRATEGY_RISK = {
    "audit_only": "low",
    "debugger_root_cause": "medium",
    "frontend_backend_parallel": "medium",
    "scout_then_execute": "medium",
    "explore_then_direct": "low",
    "audit_after_change": "medium",
    "planner_gate": "high",
    "scout_only": "low",
    "fast_direct": "low",
    "direct_single_agent": "low",
}

STRATEGY_PARALLEL = {"frontend_backend_parallel": True}

# ── Fast-path disqualifiers (only substantive patterns, not single common words) ──

FAST_PATH_DISQUALIFIERS = [
    (r'\bauth(?:entication|orization)?\b', "auth-related change"),
    (r'\bpermission\b', "permission-related change"),
    (r'\bdatabase\b', "database change"),
    (r'\bschema\s+migration\b', "schema migration"),
    (r'\bdeploy(?:ment)?\s+to\s+production\b', "production deployment"),
    (r'\bproduction\s+(?:deploy|release|bug)\b', "production change"),
    (r'\barchitecture\s+(?:decision|review|change)\b', "architecture decision"),
    (r'\brefactor\b', "multi-file refactor"),
    (r'\bpipeline\s+(?:failure|broken)\b', "pipeline failure"),
    (r'\bencrypt(?:ion)?\b', "security-related"),
    (r'\binfrastructure\s+change\b', "infrastructure change"),
]


# ── Helpers ──────────────────────────────────────────────────────

def tokenize(text):
    """Normalize to lowercase word tokens."""
    return re.findall(r'[a-z0-9]+(?:-[a-z0-9]+)*', text.lower())


def match_exact_phrases(tokens, phrases):
    """Check if any exact phrase (as word sequence) appears in token sequence."""
    text = " " + " ".join(tokens) + " "
    for phrase in phrases:
        phrase_tokens = phrase.split()
        pattern = r'\s' + r'\s+'.join(re.escape(t) for t in phrase_tokens) + r'\s'
        if re.search(pattern, text):
            return phrase
    return None


def match_single_words(tokens, words):
    """Check if any single word appears as a whole-word token."""
    token_set = set(tokens)
    return [w for w in words if w in token_set]


def has_both_domains(tokens):
    """Check if task involves both frontend and backend domains."""
    frontend = {"frontend", "ui", "component", "react", "tailwind", "css", "layout", "page", "form", "button"}
    backend = {"backend", "api", "database", "prisma", "migration", "server", "endpoint"}
    token_set = set(tokens)
    return bool(frontend & token_set) and bool(backend & token_set)


# ── Fast path check ──────────────────────────────────────────────

def check_fast_path(task, context_path=None):
    """Check whether fast path applies.

    Returns dict with applies, reason, confidence.
    """
    task_lower = task.lower()
    tokens = tokenize(task_lower)

    # Disqualifiers: substantive patterns only (not "config", "ci", "review", "plugin" alone)
    for pattern, reason in FAST_PATH_DISQUALIFIERS:
        if re.search(pattern, task_lower):
            return {"applies": False, "reason": reason, "confidence": "high"}

    # Multi-file indicators
    wide_scope_words = {"refactor", "rewrite", "restructure", "rearchitect", "migrate"}
    if wide_scope_words & set(tokens):
        return {"applies": False, "reason": "wide-scope task", "confidence": "high"}

    # Context-based heuristics
    if context_path:
        try:
            with open(context_path) as f:
                ctx = json.load(f)
            summary = ctx.get("summary", {})
            if len(summary.get("test_files", [])) > 30:
                return {"applies": False, "reason": "many test files indicate complexity", "confidence": "medium"}
        except Exception as e:
            # Log context error instead of silently ignoring
            sys.stderr.write(f"[strategy_selector] context load warning: {e}\n")

    return {"applies": True, "reason": "clear objective, low risk, narrow scope", "confidence": "high"}


# ── Strategy selection ───────────────────────────────────────────

def select_strategy(task, context_path=None):
    """Select strategy with normalized classification and confidence.

    Returns dict with strategy, agents, complexity, risk, confidence,
    reason, signals_used, and fallback status.
    """
    tokens = tokenize(task.lower())
    best_strategy = None
    best_score = 0
    best_reason = "No specific strategy matched."
    signals_used = []

    for strategy_name, defn in STRATEGY_DEFS.items():
        score = 0
        reasons = []

        # Phase 1: Exact phrase matches (highest signal)
        exact_phrases = defn.get("exact_phrases", [])
        phrase_match = match_exact_phrases(tokens, exact_phrases)
        if phrase_match:
            score += 50
            reasons.append(f"exact phrase: '{phrase_match}'")

        # Phase 2: Single word matches (moderate signal per word)
        single_words = defn.get("single_words", [])
        word_matches = match_single_words(tokens, single_words)
        if word_matches:
            word_score = 20 * len(word_matches)  # 20 per word so 2+ words cross fast-path threshold
            score += word_score
            reasons.append(f"words: {', '.join(word_matches)}")

        # Phase 3: Context signals
        signals = defn.get("signals", {})
        if context_path and signals:
            try:
                with open(context_path) as f:
                    ctx = json.load(f)
                if signals.get("test_files") and ctx.get("summary", {}).get("test_files"):
                    score += 5
                    reasons.append("has test files")
            except Exception as e:
                sys.stderr.write(f"[strategy_selector] context load warning: {e}\n")

        # Phase 4: Domain requirements
        if defn.get("requires_both_domains"):
            if not has_both_domains(tokens):
                continue  # Skip — domain requirement not met
            else:
                score += 30  # Bonus for confirmed multi-domain task
                reasons.append("both domains detected")

        if score > best_score:
            best_strategy = strategy_name
            best_score = score
            best_reason = "; ".join(reasons) if reasons else "rule matched by default"

    # Fallback
    if best_strategy is None:
        best_strategy = "direct_single_agent"
        best_score = 0
        best_reason = "Fallback: direct execution (no delegation condition matched)"
        signals_used.append("fallback")

    # Fast path override (only when no specific strategy matched at all)
    fast_path = check_fast_path(task, context_path)
    if fast_path["applies"] and best_score == 0:
        best_strategy = "fast_direct"
        best_reason = f"Fast path: {fast_path['reason']}"
        best_score = 0

    # Confidence heuristic
    if best_score >= 50:
        confidence = "high"
    elif best_score >= 10:
        confidence = "medium"
    elif fast_path.get("confidence") == "high":
        confidence = "high"
    else:
        confidence = "low"

    complexity = STRATEGY_COMPLEXITY.get(best_strategy, "medium")
    risk = STRATEGY_RISK.get(best_strategy, "medium")
    agents = STRATEGY_DEFS[best_strategy]["agents"]
    parallel = STRATEGY_PARALLEL.get(best_strategy, False)

    return {
        "strategy": best_strategy,
        "complexity": complexity,
        "risk": risk,
        "confidence": confidence,
        "agents": agents,
        "parallelizable": parallel,
        "fast_path": best_strategy == "fast_direct",
        "reason": best_reason,
        "score": best_score,
        "fallback": best_strategy == "direct_single_agent",
        "verification_gates": _verification_gates(best_strategy),
    }


def _verification_gates(strategy):
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
        "scout_only": ["scout report"],
    }
    return gates.get(strategy, ["targeted test", "lint/typecheck"])


# ── CLI ──────────────────────────────────────────────────────────

def cmd_select(args):
    result = select_strategy(args.task, args.context)
    print(json.dumps(result, indent=2, sort_keys=True))


def cmd_fast_path_check(args):
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
