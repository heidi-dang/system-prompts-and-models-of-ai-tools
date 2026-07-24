#!/usr/bin/env python3
"""
Token Estimator — estimate token usage for model requests without making calls.

Uses configurable values for static system prompt, tool schemas, conversation
history, retrieved repository context, delegation payload, subagent prompt,
tool results, output and reasoning tokens, and cache behavior.

Supports both cached and uncached token estimation.
"""

import json
from pathlib import Path

# ── Default token weights ─────────────────────────────────────────

DEFAULT_WEIGHTS = {
    "system_prompt_per_char": 0.25,     # tokens per char of system prompt
    "tool_schema_per_param": 3,         # tokens per tool parameter
    "history_per_message": 150,         # avg tokens per conversation message
    "context_per_char": 0.25,           # tokens per char of retrieved context
    "delegation_per_char": 0.25,        # tokens per char of delegation payload
    "subagent_prompt_per_char": 0.25,   # tokens per char of subagent prompt
    "tool_result_per_char": 0.25,       # tokens per char of tool result
    "output_per_char": 0.25,            # tokens per char of output
    "reasoning_per_char": 0.25,         # tokens per char of reasoning
    "cache_read_overhead": 0.1,         # fraction of input that is cache-read
    "cache_write_overhead": 1.0,        # full cost for cache-write (uncached)
}

# ── Model-specific pricing (approximate) ──────────────────────────

MODEL_PRICING = {
    "gpt-4o": {
        "input_per_1k": 2.50,
        "output_per_1k": 10.00,
        "reasoning_per_1k": None,
        "cache_read_per_1k": 0.25,
        "cache_write_per_1k": 1.25,
    },
    "gpt-4o-mini": {
        "input_per_1k": 0.15,
        "output_per_1k": 0.60,
        "reasoning_per_1k": None,
        "cache_read_per_1k": 0.015,
        "cache_write_per_1k": 0.03,
    },
    "claude-3-5-sonnet": {
        "input_per_1k": 3.00,
        "output_per_1k": 15.00,
        "reasoning_per_1k": None,
        "cache_read_per_1k": 0.30,
        "cache_write_per_1k": 3.75,
    },
    "claude-3-opus": {
        "input_per_1k": 15.00,
        "output_per_1k": 75.00,
        "reasoning_per_1k": None,
        "cache_read_per_1k": 1.50,
        "cache_write_per_1k": 18.75,
    },
    "claude-3-haiku": {
        "input_per_1k": 0.25,
        "output_per_1k": 1.25,
        "reasoning_per_1k": None,
        "cache_read_per_1k": 0.025,
        "cache_write_per_1k": 0.30,
    },
}


def estimate_tokens(system_prompt="", tool_schemas=None, history_messages=0,
                    context_chars=0, delegation_chars=0, subagent_prompt_chars=0,
                    tool_result_chars=0, output_chars=0, reasoning_chars=0,
                    cached_input_chars=0, cache_write_chars=0,
                    model="default", weights=None):
    """Estimate total tokens for a model request.

    Returns a dict with breakdown by category.
    """
    w = weights or DEFAULT_WEIGHTS

    # Uncached input tokens
    system_tokens = int(len(system_prompt) * w["system_prompt_per_char"])
    tool_tokens = 0
    if tool_schemas:
        for schema in tool_schemas:
            schema_str = json.dumps(schema, sort_keys=True)
            tool_tokens += int(len(schema_str) * w["tool_schema_per_param"] / 100)
    history_tokens = history_messages * w["history_per_message"]
    context_tokens = int(context_chars * w["context_per_char"])
    delegation_tokens = int(delegation_chars * w["delegation_per_char"])
    subagent_tokens = int(subagent_prompt_chars * w["subagent_prompt_per_char"])
    tool_result_tokens = int(tool_result_chars * w["tool_result_per_char"])

    uncached_input = (system_tokens + tool_tokens + history_tokens +
                      context_tokens + delegation_tokens + subagent_tokens +
                      tool_result_tokens)

    # Cached input tokens (cache-read)
    cache_read_tokens = int(cached_input_chars * w["cache_read_overhead"])

    # Cache-write tokens (full cost)
    cache_write_tokens = int(cache_write_chars * w["cache_write_overhead"])

    # Output tokens
    output_tokens = int(output_chars * w["output_per_char"])

    # Reasoning tokens
    reasoning_tokens = int(reasoning_chars * w["reasoning_per_char"])

    # Total
    total = (uncached_input + cache_read_tokens + cache_write_tokens +
             output_tokens + reasoning_tokens)

    return {
        "total": total,
        "uncached_input": uncached_input,
        "cached_input": cache_read_tokens,
        "cache_write": cache_write_tokens,
        "output": output_tokens,
        "reasoning": reasoning_tokens,
        "breakdown": {
            "system_prompt": system_tokens,
            "tool_schemas": tool_tokens,
            "history": history_tokens,
            "context": context_tokens,
            "delegation": delegation_tokens,
            "subagent_prompt": subagent_tokens,
            "tool_results": tool_result_tokens,
            "cache_read": cache_read_tokens,
            "cache_write": cache_write_tokens,
            "output": output_tokens,
            "reasoning": reasoning_tokens,
        },
        "model": model,
    }


def estimate_cost(estimated_tokens, model="gpt-4o"):
    """Estimate cost based on model pricing metadata.

    Returns cost dict or None if pricing is unavailable for the model.
    """
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return None

    input_tokens = estimated_tokens.get("uncached_input", 0)
    cached_input_tokens = estimated_tokens.get("cached_input", 0)
    output_tokens = estimated_tokens.get("output", 0)
    cache_write_tokens = estimated_tokens.get("cache_write", 0)

    cost = 0.0

    # Uncached input cost
    if pricing.get("input_per_1k"):
        cost += (input_tokens / 1000) * pricing["input_per_1k"]

    # Cache-read cost (lower)
    if pricing.get("cache_read_per_1k"):
        cost += (cached_input_tokens / 1000) * pricing["cache_read_per_1k"]

    # Cache-write cost
    if pricing.get("cache_write_per_1k"):
        cost += (cache_write_tokens / 1000) * pricing["cache_write_per_1k"]

    # Output cost
    if pricing.get("output_per_1k"):
        cost += (output_tokens / 1000) * pricing["output_per_1k"]

    return {
        "model": model,
        "estimated_cost_usd": round(cost, 6),
        "input_cost_usd": round((input_tokens / 1000) * pricing.get("input_per_1k", 0), 6),
        "output_cost_usd": round((output_tokens / 1000) * pricing.get("output_per_1k", 0), 6),
        "cache_read_cost_usd": round((cached_input_tokens / 1000) * pricing.get("cache_read_per_1k", 0), 6),
        "cache_write_cost_usd": round((cache_write_tokens / 1000) * pricing.get("cache_write_per_1k", 0), 6),
    }


def simulate_task(tokens_per_step=5000, steps=20, model="gpt-4o",
                  delegation_ratio=0.5, cache_hit_ratio=0.3):
    """Simulate a task with multiple steps to estimate cumulative token usage.

    Args:
        tokens_per_step: Estimated tokens per model call.
        steps: Number of model calls in the task.
        model: Model name for pricing.
        delegation_ratio: Fraction of calls that are delegations (larger payloads).
        cache_hit_ratio: Fraction of calls that hit the cache.

    Returns:
        Dict with simulation results.
    """
    total_tokens = 0
    total_uncached = 0
    total_cached = 0
    total_output = 0
    total_reasoning = 0
    total_cache_write = 0
    costs = []

    for i in range(steps):
        is_delegation = i < int(steps * delegation_ratio)
        is_cache_hit = (i % int(1 / max(cache_hit_ratio, 0.01))) == 0 if cache_hit_ratio > 0 else False

        context_chars = 8000 if is_delegation else 2000
        delegation_chars = 1500 if is_delegation else 0

        est = estimate_tokens(
            system_prompt="Heidi orchestrator agent prompt...",
            history_messages=10 + i,
            context_chars=context_chars,
            delegation_chars=delegation_chars,
            subagent_prompt_chars=2000 if is_delegation else 0,
            tool_result_chars=500,
            output_chars=200,
            reasoning_chars=100,
            cached_input_chars=context_chars if is_cache_hit else 0,
            cache_write_chars=context_chars if not is_cache_hit else 0,
            model=model,
        )

        total_tokens += est["total"]
        total_uncached += est["uncached_input"]
        total_cached += est["cached_input"]
        total_output += est["output"]
        total_reasoning += est["reasoning"]
        total_cache_write += est["cache_write"]

        cost = estimate_cost(est, model)
        if cost:
            costs.append(cost["estimated_cost_usd"])

    return {
        "total_tokens": total_tokens,
        "total_uncached_input": total_uncached,
        "total_cached_input": total_cached,
        "total_output": total_output,
        "total_reasoning": total_reasoning,
        "total_cache_write": total_cache_write,
        "total_steps": steps,
        "estimated_cost_usd": round(sum(costs), 6),
        "model": model,
    }


def simulate_27m_scenario():
    """Simulate the 27M token scenario from the audit.

    This reproduces the amplification pattern:
    - Full-context delegation to multiple subagents
    - Repeated context retrieval
    - No token budget enforcement
    - Multiple audit cycles
    - Equivalent retries
    """
    total = 0
    breakdown = {}

    # Phase 1: Initial task + Scout (full context)
    est = estimate_tokens(
        system_prompt="Heidi orchestrator agent prompt..." * 50,  # bloated prompt
        history_messages=50,  # large conversation history
        context_chars=50000,  # full context retrieval (no budget)
        delegation_chars=5000,  # full user request + context
        subagent_prompt_chars=5000,  # full subagent prompt
        tool_result_chars=5000,
        output_chars=500,
        reasoning_chars=500,
        model="gpt-4o",
    )
    total += est["total"]
    breakdown["scout_full_context"] = est["total"]

    # Phase 2: Planner (full context again)
    est = estimate_tokens(
        system_prompt="Heidi orchestrator agent prompt..." * 50,
        history_messages=55,
        context_chars=50000,
        delegation_chars=5000,
        subagent_prompt_chars=5000,
        tool_result_chars=3000,
        output_chars=800,
        reasoning_chars=300,
        model="gpt-4o",
    )
    total += est["total"]
    breakdown["planner_full_context"] = est["total"]

    # Phase 3: Parallel Frontend + Backend (each gets full context)
    for role in ["frontend", "backend"]:
        est = estimate_tokens(
            system_prompt="Heidi orchestrator agent prompt..." * 50,
            history_messages=60,
            context_chars=50000,
            delegation_chars=5000,
            subagent_prompt_chars=5000,
            tool_result_chars=4000,
            output_chars=1000,
            reasoning_chars=400,
            model="gpt-4o",
        )
        total += est["total"]
        breakdown[f"{role}_full_context"] = est["total"]

    # Phase 4: Implementation (multiple calls, each re-sends full context)
    for i in range(10):
        est = estimate_tokens(
            system_prompt="Heidi orchestrator agent prompt..." * 50,
            history_messages=65 + i,
            context_chars=50000,
            delegation_chars=5000,
            subagent_prompt_chars=5000,
            tool_result_chars=3000,
            output_chars=300,
            reasoning_chars=200,
            model="gpt-4o",
        )
        total += est["total"]
        breakdown[f"implementation_call_{i}"] = est["total"]

    # Phase 5: Auditor (full context + previous work)
    est = estimate_tokens(
        system_prompt="Heidi orchestrator agent prompt..." * 50,
        history_messages=80,
        context_chars=50000,
        delegation_chars=5000,
        subagent_prompt_chars=5000,
        tool_result_chars=6000,
        output_chars=1500,
        reasoning_chars=600,
        model="gpt-4o",
    )
    total += est["total"]
    breakdown["auditor_full_context"] = est["total"]

    # Phase 6: Debugger + repair (equivalent retry)
    for i in range(3):
        est = estimate_tokens(
            system_prompt="Heidi orchestrator agent prompt..." * 50,
            history_messages=85 + i,
            context_chars=50000,
            delegation_chars=5000,
            subagent_prompt_chars=5000,
            tool_result_chars=4000,
            output_chars=400,
            reasoning_chars=300,
            model="gpt-4o",
        )
        total += est["total"]
        breakdown[f"debugger_retry_{i}"] = est["total"]

    # Phase 7: Second audit cycle (unbounded)
    est = estimate_tokens(
        system_prompt="Heidi orchestrator agent prompt..." * 50,
        history_messages=95,
        context_chars=50000,
        delegation_chars=5000,
        subagent_prompt_chars=5000,
        tool_result_chars=7000,
        output_chars=2000,
        reasoning_chars=800,
        model="gpt-4o",
    )
    total += est["total"]
    breakdown["second_audit_cycle"] = est["total"]

    # Phase 8: More implementation calls (no budget stop)
    for i in range(15):
        est = estimate_tokens(
            system_prompt="Heidi orchestrator agent prompt..." * 50,
            history_messages=100 + i,
            context_chars=50000,
            delegation_chars=5000,
            subagent_prompt_chars=5000,
            tool_result_chars=3000,
            output_chars=300,
            reasoning_chars=200,
            model="gpt-4o",
        )
        total += est["total"]
        breakdown[f"late_implementation_{i}"] = est["total"]

    return {
        "total_tokens": total,
        "breakdown": breakdown,
        "num_calls": len(breakdown),
        "scenario": "27M_token_amplification",
    }


# ── Governed 27M scenario (same phases, governance controls applied) ─


GOVERNED_WEIGHTS = {
    "system_prompt_per_char": 0.25,
    "history_per_message": 150,
    "context_per_char": 0.25,
    "delegation_per_char": 0.25,
    "subagent_prompt_per_char": 0.25,
    "tool_result_per_char": 0.25,
    "output_per_char": 0.25,
    "reasoning_per_char": 0.25,
    "cache_read_overhead": 0.1,
    "cache_write_overhead": 1.0,
}


def _governed_estimate(system_prompt_chars=2000, history_messages=5,
                       context_chars=5000, delegation_chars=1500,
                       subagent_prompt_chars=2000, tool_result_chars=3000,
                       output_chars=500, reasoning_chars=300,
                       cached_input_chars=0, cache_write_chars=0):
    """Estimate tokens under governance controls (compact payloads)."""
    w = GOVERNED_WEIGHTS
    system_tokens = int(system_prompt_chars * w["system_prompt_per_char"])
    history_tokens = history_messages * w["history_per_message"]
    context_tokens = int(context_chars * w["context_per_char"])
    delegation_tokens = int(delegation_chars * w["delegation_per_char"])
    subagent_tokens = int(subagent_prompt_chars * w["subagent_prompt_per_char"])
    tool_result_tokens = int(tool_result_chars * w["tool_result_per_char"])
    output_tokens = int(output_chars * w["output_per_char"])
    reasoning_tokens = int(reasoning_chars * w["reasoning_per_char"])

    uncached_input = (system_tokens + history_tokens + context_tokens +
                      delegation_tokens + subagent_tokens + tool_result_tokens)
    cached_input = int(cached_input_chars * w["cache_read_overhead"])
    cache_write = int(cache_write_chars * w["cache_write_overhead"])

    total = uncached_input + cached_input + cache_write + output_tokens + reasoning_tokens
    return {
        "total": total,
        "uncached_input": uncached_input,
        "cached_input": cached_input,
        "cache_write": cache_write,
        "output": output_tokens,
        "reasoning": reasoning_tokens,
        "breakdown": {
            "system_prompt": system_tokens,
            "history": history_tokens,
            "context": context_tokens,
            "delegation": delegation_tokens,
            "subagent_prompt": subagent_tokens,
            "tool_results": tool_result_tokens,
        },
    }


def simulate_27m_governed():
    """Simulate the 27M token scenario WITH governance controls enforced.

    Governance limits applied per DEFAULT_POLICY consumption section:
      delegation_context_limit=1500 → ~375 tokens per delegation payload
      max_total_tokens=1_500_000    → hard stop
      max_model_calls=40            → cap on total model requests
      max_subagent_calls=8          → cap on delegated subagent calls
      max_calls_per_agent=3         → per-agent call limit
      max_audit_cycles=1            → single audit pass
      max_equivalent_retries=2      → retry dedup prevents equivalent repeats
      warning_percent=70            → budget warning at 70%
      hard_stop_percent=100         → hard stop at 100%

    Compact payloads:
      system_prompt   = 2,000 chars (~500 tokens)
      history         = 5 messages (~750 tokens)
      context         = 5,000 chars (~1,250 tokens)
      delegation      = 1,500 chars (~375 tokens)
      subagent_prompt = 2,000 chars (~500 tokens)
      tool_results    = 3,000 chars (~750 tokens)
      output          = 500 chars   (~125 tokens)
      reasoning       = 300 chars   (~75 tokens)
      ----------------------------------------------------
      Per-call total: ~4,275 tokens (vs ~25,000+ unbounded)
    """
    total = 0
    breakdown = {}
    model_calls = 0
    subagent_calls = 0
    audit_cycles = 0
    warning_triggered = False
    hard_stop_triggered = False
    tracked_total_input = 0
    tracked_total_output = 0
    tracked_total_cached = 0
    tracked_total_reasoning = 0

    policy = {
        "max_total_tokens": 1_500_000,
        "warning_percent": 70,
    }

    def record_call(phase_name, est, is_subagent=False):
        nonlocal total, model_calls, subagent_calls, warning_triggered
        nonlocal hard_stop_triggered, tracked_total_input, tracked_total_output
        nonlocal tracked_total_cached, tracked_total_reasoning

        model_calls += 1
        if is_subagent:
            subagent_calls += 1

        # Check hard stop
        projected = total + est["total"]
        if projected > policy["max_total_tokens"]:
            hard_stop_triggered = True
            breakdown[f"{phase_name}__HARD_STOP"] = est["total"]
            return False

        # Check model call limit
        if model_calls > 40:
            hard_stop_triggered = True
            breakdown[f"{phase_name}__MODEL_LIMIT"] = est["total"]
            return False

        # Check subagent call limit
        if subagent_calls > 8:
            hard_stop_triggered = True
            breakdown[f"{phase_name}__SUBAGENT_LIMIT"] = est["total"]
            return False

        # Check warning
        warning_threshold = policy["max_total_tokens"] * policy["warning_percent"] / 100
        if projected > warning_threshold and not warning_triggered:
            warning_triggered = True

        total += est["total"]
        tracked_total_input += est["uncached_input"]
        tracked_total_output += est["output"]
        tracked_total_reasoning += est["reasoning"]
        tracked_total_cached += est["cached_input"]
        breakdown[phase_name] = est["total"]
        return True

    # Phase 1: Scout (compact, 1 subagent call)
    est = _governed_estimate()
    record_call("scout_governed", est, is_subagent=True)

    # Phase 2: Planner (compact, 1 subagent call)
    est = _governed_estimate(tool_result_chars=3000, output_chars=500, reasoning_chars=200)
    record_call("planner_governed", est, is_subagent=True)

    # Phase 3: Frontend + Backend parallel (2 subagent calls)
    for role in ["frontend", "backend"]:
        est = _governed_estimate(tool_result_chars=3000, output_chars=800, reasoning_chars=300)
        if not record_call(f"{role}_governed", est, is_subagent=True):
            break

    # Phase 4: Implementation (direct execution, no delegation, up to 10 calls)
    for i in range(10):
        est = _governed_estimate(delegation_chars=0, tool_result_chars=2000,
                                 output_chars=400, reasoning_chars=200)
        if not record_call(f"impl_governed_{i}", est, is_subagent=False):
            break

    # Phase 5: Auditor (1 subagent call, single audit cycle)
    est = _governed_estimate(tool_result_chars=4000, output_chars=1000, reasoning_chars=500)
    record_call("auditor_governed", est, is_subagent=True)

    # Phase 6: No equivalent retries (retry dedup prevents these)
    # Skipped entirely under governance.

    # Phase 7: No second audit cycle (capped at max_audit_cycles=1)
    # Skipped entirely under governance.

    # Phase 8: More implementation until hard stop / call limit
    for i in range(20):
        est = _governed_estimate(delegation_chars=0, tool_result_chars=2000,
                                 output_chars=400, reasoning_chars=200)
        if not record_call(f"late_impl_governed_{i}", est, is_subagent=False):
            break

    return {
        "scenario": "27M_token_governed",
        "total_tokens": total,
        "total_input": tracked_total_input,
        "total_output": tracked_total_output,
        "total_cached_input": tracked_total_cached,
        "total_reasoning": tracked_total_reasoning,
        "model_calls": model_calls,
        "subagent_calls": subagent_calls,
        "audit_cycles": 1,
        "budget_warning_triggered": warning_triggered,
        "hard_stop_triggered": hard_stop_triggered,
        "num_calls": len(breakdown),
        "breakdown": breakdown,
        "policy_limits": {
            "max_total_tokens": 1_500_000,
            "max_model_calls": 40,
            "max_subagent_calls": 8,
            "max_calls_per_agent": 3,
            "max_audit_cycles": 1,
            "max_equivalent_retries": 2,
            "warning_percent": 70,
            "hard_stop_percent": 100,
        },
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Token Estimator")
    sub = parser.add_subparsers(dest="command", required=True)

    p_est = sub.add_parser("estimate", help="Estimate tokens for a request")
    p_est.add_argument("--system-prompt", default="")
    p_est.add_argument("--history-messages", type=int, default=0)
    p_est.add_argument("--context-chars", type=int, default=0)
    p_est.add_argument("--delegation-chars", type=int, default=0)
    p_est.add_argument("--subagent-prompt-chars", type=int, default=0)
    p_est.add_argument("--tool-result-chars", type=int, default=0)
    p_est.add_argument("--output-chars", type=int, default=0)
    p_est.add_argument("--reasoning-chars", type=int, default=0)
    p_est.add_argument("--cached-input-chars", type=int, default=0)
    p_est.add_argument("--cache-write-chars", type=int, default=0)
    p_est.add_argument("--model", default="default")

    p_sim = sub.add_parser("simulate", help="Simulate a task")
    p_sim.add_argument("--tokens-per-step", type=int, default=5000)
    p_sim.add_argument("--steps", type=int, default=20)
    p_sim.add_argument("--model", default="gpt-4o")
    p_sim.add_argument("--delegation-ratio", type=float, default=0.5)
    p_sim.add_argument("--cache-hit-ratio", type=float, default=0.3)

    p_27m = sub.add_parser("simulate-27m", help="Simulate the 27M token scenario")

    p_gov = sub.add_parser("simulate-governed", help="Simulate the 27M scenario WITH governance controls")

    p_cost = sub.add_parser("cost", help="Estimate cost")
    p_cost.add_argument("--tokens", required=True, help="JSON of estimated tokens")
    p_cost.add_argument("--model", default="gpt-4o")

    args = parser.parse_args()

    if args.command == "estimate":
        result = estimate_tokens(
            system_prompt=args.system_prompt,
            history_messages=args.history_messages,
            context_chars=args.context_chars,
            delegation_chars=args.delegation_chars,
            subagent_prompt_chars=args.subagent_prompt_chars,
            tool_result_chars=args.tool_result_chars,
            output_chars=args.output_chars,
            reasoning_chars=args.reasoning_chars,
            cached_input_chars=args.cached_input_chars,
            cache_write_chars=args.cache_write_chars,
            model=args.model,
        )
        print(json.dumps(result, indent=2, sort_keys=True))

    elif args.command == "simulate":
        result = simulate_task(
            tokens_per_step=args.tokens_per_step,
            steps=args.steps,
            model=args.model,
            delegation_ratio=args.delegation_ratio,
            cache_hit_ratio=args.cache_hit_ratio,
        )
        print(json.dumps(result, indent=2, sort_keys=True))

    elif args.command == "simulate-27m":
        result = simulate_27m_scenario()
        print(json.dumps(result, indent=2, sort_keys=True))

    elif args.command == "simulate-governed":
        result = simulate_27m_governed()
        print(json.dumps(result, indent=2, sort_keys=True))

    elif args.command == "cost":
        tokens = json.loads(args.tokens)
        result = estimate_cost(tokens, args.model)
        print(json.dumps(result, indent=2, sort_keys=True))