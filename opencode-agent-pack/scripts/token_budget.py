#!/usr/bin/env python3
"""
Token Budget Manager — enforceable per-task consumption limits for Heidi.

Tracks token consumption for the current task, including parent Heidi calls
and child-agent calls. Enforces configurable limits and produces bounded
partial-completion reports when limits are reached.

Usage:
    python3 token_budget.py init --task-id <id> --policy <policy.json>
    python3 token_budget.py record --task-id <id> --agent <agent> --strategy <strategy>
        --input-tokens <n> --output-tokens <n> [--reasoning-tokens <n>]
        [--cached-input <n>] [--cache-write <n>] [--model <name>]
    python3 token_budget.py status --task-id <id>
    python3 token_budget.py report --task-id <id>
"""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# ── Default consumption policy ──────────────────────────────────────────

DEFAULT_POLICY = {
    "consumption": {
        "max_total_tokens": 1_500_000,
        "max_input_tokens_per_request": 100_000,
        "max_output_tokens_per_request": 8_000,
        "max_reasoning_tokens_per_request": 12_000,
        "max_model_calls": 40,
        "max_subagent_calls": 8,
        "max_calls_per_agent": 3,
        "max_parallel_agents": 2,
        "max_audit_cycles": 1,
        "max_equivalent_retries": 2,
        "warning_percent": 70,
        "hard_stop_percent": 100,
        "delegation_context_limit": 1500,
        "delegation_context_max": 4000,
    }
}

# ── Conservative tokenizer approximation ─────────────────────────────────

# Rough tokens-per-character ratios for common models.
# Used when provider usage metadata is missing.
TOKENS_PER_CHAR_APPROX = {
    "default": 4.0,       # ~4 chars per token for English text
    "gpt-4": 3.5,
    "gpt-4o": 3.5,
    "gpt-4o-mini": 4.0,
    "claude-3-5-sonnet": 3.8,
    "claude-3-opus": 3.5,
    "claude-3-haiku": 4.2,
    "anthropic/claude-3-5-sonnet": 3.8,
    "anthropic/claude-3-opus": 3.5,
    "anthropic/claude-3-haiku": 4.2,
}


def estimate_tokens_from_text(text, model="default"):
    """Conservative token estimate from raw text when provider metadata is missing."""
    ratio = TOKENS_PER_CHAR_APPROX.get(model, TOKENS_PER_CHAR_APPROX["default"])
    return max(1, int(len(text) / ratio))


def estimate_tokens_from_request(request_dict, model="default"):
    """Estimate tokens from a serialized request dict."""
    serialized = json.dumps(request_dict, sort_keys=True, default=str)
    return estimate_tokens_from_text(serialized, model)


# ── Budget Manager ───────────────────────────────────────────────────────

class TokenBudgetManager:
    """Tracks and enforces per-task token consumption limits."""

    def __init__(self, policy=None, task_id=None, ledger_path=None):
        self.policy = policy or DEFAULT_POLICY["consumption"]
        self.task_id = task_id or "unknown"
        self.ledger_path = ledger_path

        # Usage accumulators
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_reasoning_tokens = 0
        self.total_cached_input_tokens = 0
        self.total_cache_write_tokens = 0
        self.total_tokens = 0

        # Call tracking
        self.model_calls = 0
        self.subagent_calls = 0
        self.calls_by_agent = {}       # agent -> count
        self.calls_by_strategy = {}    # strategy -> count
        self.calls_by_model = {}       # model -> count

        # Per-request tracking (for dedup and largest-request detection)
        self.requests = []             # list of request records
        self.request_fingerprints = set()

        # Budget events
        self.events = []               # list of budget event dicts

        # Warning/hard-stop state
        self.warning_triggered = False
        self.hard_stop_triggered = False
        self.partial_completion = None

        # Audit cycle tracking
        self.audit_cycles = 0

        # Equivalent retry tracking
        self.retry_fingerprints = {}   # fingerprint -> count

    # ── Recording ──────────────────────────────────────────────────────

    def record_request(self, agent, strategy, input_tokens=None, output_tokens=None,
                       reasoning_tokens=None, cached_input=None, cache_write=None,
                       model="unknown", request_dict=None, fingerprint=None):
        """Record a model request's token usage.

        Returns (accepted: bool, reason: str).
        If accepted is False, the request should not be made.
        """
        # Check hard stop
        if self.hard_stop_triggered:
            return False, "hard_stop: budget already exceeded"

        # Check per-request limits
        if input_tokens is not None and input_tokens > self.policy["max_input_tokens_per_request"]:
            return False, f"hard_stop: input tokens ({input_tokens}) exceeds per-request limit ({self.policy['max_input_tokens_per_request']})"

        if output_tokens is not None and output_tokens > self.policy["max_output_tokens_per_request"]:
            return False, f"hard_stop: output tokens ({output_tokens}) exceeds per-request limit ({self.policy['max_output_tokens_per_request']})"

        if reasoning_tokens is not None and reasoning_tokens > self.policy["max_reasoning_tokens_per_request"]:
            return False, f"hard_stop: reasoning tokens ({reasoning_tokens}) exceeds per-request limit ({self.policy['max_reasoning_tokens_per_request']})"

        # Conservative estimate if tokens not provided
        if input_tokens is None and request_dict is not None:
            input_tokens = estimate_tokens_from_request(request_dict, model)
        if output_tokens is None:
            output_tokens = 0
        if reasoning_tokens is None:
            reasoning_tokens = 0
        if cached_input is None:
            cached_input = 0
        if cache_write is None:
            cache_write = 0

        # Check if this would exceed total budget
        projected_total = self.total_tokens + input_tokens + output_tokens + reasoning_tokens
        max_total = self.policy["max_total_tokens"]

        if projected_total > max_total:
            self.hard_stop_triggered = True
            self._record_event("hard_stop", agent, strategy, {
                "reason": "projected_total_exceeds_max",
                "projected_total": projected_total,
                "max_total": max_total,
            })
            return False, f"hard_stop: projected total ({projected_total}) exceeds max ({max_total})"

        # Check warning threshold
        warning_threshold = self.policy["max_total_tokens"] * self.policy["warning_percent"] / 100
        if projected_total > warning_threshold and not self.warning_triggered:
            self.warning_triggered = True
            self._record_event("warning", agent, strategy, {
                "reason": "warning_threshold_exceeded",
                "projected_total": projected_total,
                "warning_threshold": warning_threshold,
            })

        # Check model call limit
        if self.model_calls >= self.policy["max_model_calls"]:
            return False, f"hard_stop: model calls ({self.model_calls}) exceeds max ({self.policy['max_model_calls']})"

        # Check per-agent call limit
        agent_count = self.calls_by_agent.get(agent, 0)
        if agent_count >= self.policy["max_calls_per_agent"]:
            return False, f"hard_stop: agent '{agent}' calls ({agent_count}) exceeds max ({self.policy['max_calls_per_agent']})"

        # Check subagent call limit (for non-heidi agents)
        if agent != "heidi":
            if self.subagent_calls >= self.policy["max_subagent_calls"]:
                return False, f"hard_stop: subagent calls ({self.subagent_calls}) at max ({self.policy['max_subagent_calls']})"
            self.subagent_calls += 1

        # Record the request
        self.model_calls += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_reasoning_tokens += reasoning_tokens
        self.total_cached_input_tokens += cached_input
        self.total_cache_write_tokens += cache_write
        self.total_tokens = (self.total_input_tokens + self.total_output_tokens +
                             self.total_reasoning_tokens)

        self.calls_by_agent[agent] = self.calls_by_agent.get(agent, 0) + 1
        self.calls_by_strategy[strategy] = self.calls_by_strategy.get(strategy, 0) + 1
        self.calls_by_model[model] = self.calls_by_model.get(model, 0) + 1

        # Track largest request
        request_record = {
            "agent": agent,
            "strategy": strategy,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens,
            "cached_input": cached_input,
            "cache_write": cache_write,
            "total_tokens": input_tokens + output_tokens + reasoning_tokens,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if fingerprint:
            request_record["fingerprint"] = fingerprint
        self.requests.append(request_record)

        # Track fingerprint for dedup
        if fingerprint:
            self.request_fingerprints.add(fingerprint)

        return True, "accepted"

    def record_audit_cycle(self):
        """Record an audit cycle. Returns True if allowed, False if limit reached."""
        if self.audit_cycles >= self.policy["max_audit_cycles"]:
            self._record_event("audit_cycle_blocked", "heidi", "audit", {
                "reason": "max_audit_cycles_reached",
                "audit_cycles": self.audit_cycles,
                "max_audit_cycles": self.policy["max_audit_cycles"],
            })
            return False
        self.audit_cycles += 1
        return True

    def check_retry(self, fingerprint):
        """Check if a retry with this fingerprint is allowed.

        Returns (allowed: bool, reason: str).
        """
        count = self.retry_fingerprints.get(fingerprint, 0)
        if count >= self.policy["max_equivalent_retries"]:
            return False, f"circuit_breaker: equivalent retry '{fingerprint[:16]}...' exceeded max ({self.policy['max_equivalent_retries']})"
        self.retry_fingerprints[fingerprint] = count + 1
        return True, "allowed"

    def check_delegation_allowed(self):
        """Check if optional delegation is still allowed.

        Returns True if delegation is allowed, False if warning threshold reached.
        """
        if self.warning_triggered:
            return False
        return True

    def check_parallel_allowed(self):
        """Check if parallel agent execution is allowed."""
        active_parallel = sum(1 for a, c in self.calls_by_agent.items()
                              if a != "heidi" and c > 0)
        return active_parallel < self.policy["max_parallel_agents"]

    def get_budget_percentage(self):
        """Return percentage of total budget consumed."""
        return (self.total_tokens / self.policy["max_total_tokens"] * 100) if self.policy["max_total_tokens"] > 0 else 0

    def get_largest_request(self):
        """Return the largest request by total tokens."""
        if not self.requests:
            return None
        return max(self.requests, key=lambda r: r["total_tokens"])

    def get_partial_completion_report(self):
        """Produce a bounded partial-completion report when hard stop is triggered."""
        return {
            "task_id": self.task_id,
            "status": "partial_completion",
            "reason": self._get_stop_reason(),
            "budget_consumed_percent": round(self.get_budget_percentage(), 1),
            "total_tokens": self.total_tokens,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_reasoning_tokens": self.total_reasoning_tokens,
            "total_cached_input_tokens": self.total_cached_input_tokens,
            "total_cache_write_tokens": self.total_cache_write_tokens,
            "model_calls": self.model_calls,
            "subagent_calls": self.subagent_calls,
            "calls_by_agent": dict(self.calls_by_agent),
            "calls_by_strategy": dict(self.calls_by_strategy),
            "calls_by_model": dict(self.calls_by_model),
            "audit_cycles": self.audit_cycles,
            "warning_triggered": self.warning_triggered,
            "hard_stop_triggered": self.hard_stop_triggered,
            "largest_request": self.get_largest_request(),
            "events": self.events,
        }

    # ── Persistence ────────────────────────────────────────────────────

    def save(self, path=None):
        """Save budget state to a JSON file."""
        path = path or self.ledger_path
        if not path:
            return
        data = self.to_dict()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".json.tmp")
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(data, f, indent=2, sort_keys=True)
            os.replace(tmp_path, path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def load(self, path):
        """Load budget state from a JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        self._from_dict(data)

    def to_dict(self):
        return {
            "schema_version": "1.0.0",
            "task_id": self.task_id,
            "policy": self.policy,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_reasoning_tokens": self.total_reasoning_tokens,
            "total_cached_input_tokens": self.total_cached_input_tokens,
            "total_cache_write_tokens": self.total_cache_write_tokens,
            "total_tokens": self.total_tokens,
            "model_calls": self.model_calls,
            "subagent_calls": self.subagent_calls,
            "calls_by_agent": dict(self.calls_by_agent),
            "calls_by_strategy": dict(self.calls_by_strategy),
            "calls_by_model": dict(self.calls_by_model),
            "audit_cycles": self.audit_cycles,
            "warning_triggered": self.warning_triggered,
            "hard_stop_triggered": self.hard_stop_triggered,
            "requests": self.requests,
            "events": self.events,
            "retry_fingerprints": dict(self.retry_fingerprints),
        }

    def _from_dict(self, data):
        self.task_id = data.get("task_id", self.task_id)
        self.policy = data.get("policy", self.policy)
        self.total_input_tokens = data.get("total_input_tokens", 0)
        self.total_output_tokens = data.get("total_output_tokens", 0)
        self.total_reasoning_tokens = data.get("total_reasoning_tokens", 0)
        self.total_cached_input_tokens = data.get("total_cached_input_tokens", 0)
        self.total_cache_write_tokens = data.get("total_cache_write_tokens", 0)
        self.total_tokens = data.get("total_tokens", 0)
        self.model_calls = data.get("model_calls", 0)
        self.subagent_calls = data.get("subagent_calls", 0)
        self.calls_by_agent = data.get("calls_by_agent", {})
        self.calls_by_strategy = data.get("calls_by_strategy", {})
        self.calls_by_model = data.get("calls_by_model", {})
        self.audit_cycles = data.get("audit_cycles", 0)
        self.warning_triggered = data.get("warning_triggered", False)
        self.hard_stop_triggered = data.get("hard_stop_triggered", False)
        self.requests = data.get("requests", [])
        self.events = data.get("events", [])
        self.retry_fingerprints = data.get("retry_fingerprints", {})

    # ── Internal ───────────────────────────────────────────────────────

    def _record_event(self, event_type, agent, strategy, details):
        event = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "strategy": strategy,
            "details": details,
        }
        self.events.append(event)

    def _get_stop_reason(self):
        if self.hard_stop_triggered:
            if self.total_tokens >= self.policy["max_total_tokens"]:
                return "total_token_limit_reached"
            if self.model_calls >= self.policy["max_model_calls"]:
                return "max_model_calls_reached"
            if self.subagent_calls >= self.policy["max_subagent_calls"]:
                return "max_subagent_calls_reached"
            return "hard_stop_triggered"
        if self.warning_triggered:
            return "warning_threshold_reached"
        return "unknown"


# ── CLI ──────────────────────────────────────────────────────────────────

def cmd_init(args):
    """Initialize a budget for a task."""
    policy_path = args.policy
    policy = DEFAULT_POLICY["consumption"]
    if policy_path and os.path.exists(policy_path):
        with open(policy_path) as f:
            loaded = json.load(f)
            policy = loaded.get("consumption", policy)

    budget = TokenBudgetManager(policy=policy, task_id=args.task_id)

    os.makedirs(os.path.dirname(args.budget_file) or ".", exist_ok=True)
    budget.save(args.budget_file)
    print(f"Budget initialized for task {args.task_id}")
    print(f"  Max total tokens: {policy['max_total_tokens']}")
    print(f"  Max input/request: {policy['max_input_tokens_per_request']}")
    print(f"  Max output/request: {policy['max_output_tokens_per_request']}")
    print(f"  Max model calls: {policy['max_model_calls']}")
    print(f"  Max subagent calls: {policy['max_subagent_calls']}")


def cmd_record(args):
    """Record a model request's token usage."""
    budget_file = args.budget_file
    if not os.path.exists(budget_file):
        print(f"Error: budget file not found: {budget_file}", file=sys.stderr)
        sys.exit(1)

    budget = TokenBudgetManager(task_id=args.task_id)
    budget.load(budget_file)

    # Build request dict for estimation if tokens not provided
    request_dict = None
    if args.request_data:
        try:
            request_dict = json.loads(args.request_data)
        except json.JSONDecodeError:
            pass

    accepted, reason = budget.record_request(
        agent=args.agent,
        strategy=args.strategy,
        input_tokens=args.input_tokens,
        output_tokens=args.output_tokens,
        reasoning_tokens=args.reasoning_tokens,
        cached_input=args.cached_input,
        cache_write=args.cache_write,
        model=args.model,
        request_dict=request_dict,
        fingerprint=args.fingerprint,
    )

    budget.save(budget_file)

    if accepted:
        print(f"Recorded: agent={args.agent} strategy={args.strategy} model={args.model}")
        print(f"  Input: {args.input_tokens or 'estimated'}, Output: {args.output_tokens or 0}, "
              f"Reasoning: {args.reasoning_tokens or 0}")
        print(f"  Total tokens: {budget.total_tokens} / {budget.policy['max_total_tokens']}")
        print(f"  Budget: {budget.get_budget_percentage():.1f}%")
    else:
        print(f"REJECTED: {reason}", file=sys.stderr)
        sys.exit(1)


def cmd_status(args):
    """Show current budget status."""
    budget_file = args.budget_file
    if not os.path.exists(budget_file):
        print(f"Error: budget file not found: {budget_file}", file=sys.stderr)
        sys.exit(1)

    budget = TokenBudgetManager(task_id=args.task_id)
    budget.load(budget_file)

    print(f"Task: {budget.task_id}")
    print(f"Total tokens: {budget.total_tokens} / {budget.policy['max_total_tokens']}")
    print(f"  Input: {budget.total_input_tokens}")
    print(f"  Output: {budget.total_output_tokens}")
    print(f"  Reasoning: {budget.total_reasoning_tokens}")
    print(f"  Cached input: {budget.total_cached_input_tokens}")
    print(f"  Cache write: {budget.total_cache_write_tokens}")
    print(f"Budget: {budget.get_budget_percentage():.1f}%")
    print(f"Model calls: {budget.model_calls} / {budget.policy['max_model_calls']}")
    print(f"Subagent calls: {budget.subagent_calls} / {budget.policy['max_subagent_calls']}")
    print(f"Warning triggered: {budget.warning_triggered}")
    print(f"Hard stop triggered: {budget.hard_stop_triggered}")
    print(f"Delegation allowed: {budget.check_delegation_allowed()}")
    print(f"Parallel allowed: {budget.check_parallel_allowed()}")
    for agent, count in sorted(budget.calls_by_agent.items()):
        print(f"  Agent {agent}: {count} calls")


def cmd_report(args):
    """Generate a budget report."""
    budget_file = args.budget_file
    if not os.path.exists(budget_file):
        print(f"Error: budget file not found: {budget_file}", file=sys.stderr)
        sys.exit(1)

    budget = TokenBudgetManager(task_id=args.task_id)
    budget.load(budget_file)

    report = budget.get_partial_completion_report()
    print(json.dumps(report, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description="Token Budget Manager")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize a budget for a task")
    p_init.add_argument("--task-id", required=True)
    p_init.add_argument("--policy", default=None, help="Path to policy JSON file")
    p_init.add_argument("--budget-file", required=True, help="Path to budget state file")

    p_record = sub.add_parser("record", help="Record a model request")
    p_record.add_argument("--budget-file", required=True)
    p_record.add_argument("--task-id", required=True)
    p_record.add_argument("--agent", required=True)
    p_record.add_argument("--strategy", required=True)
    p_record.add_argument("--input-tokens", type=int, default=None)
    p_record.add_argument("--output-tokens", type=int, default=None)
    p_record.add_argument("--reasoning-tokens", type=int, default=None)
    p_record.add_argument("--cached-input", type=int, default=None)
    p_record.add_argument("--cache-write", type=int, default=None)
    p_record.add_argument("--model", default="unknown")
    p_record.add_argument("--request-data", default=None, help="JSON request dict for estimation")
    p_record.add_argument("--fingerprint", default=None)

    p_status = sub.add_parser("status", help="Show budget status")
    p_status.add_argument("--budget-file", required=True)
    p_status.add_argument("--task-id", required=True)

    p_report = sub.add_parser("report", help="Generate budget report")
    p_report.add_argument("--budget-file", required=True)
    p_report.add_argument("--task-id", required=True)

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "record":
        cmd_record(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "report":
        cmd_report(args)


if __name__ == "__main__":
    main()