#!/usr/bin/env python3
"""Tests for token governance: budget manager, estimator, delegation handoff."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "opencode-agent-pack" / "scripts"))

from token_budget import TokenBudgetManager, DEFAULT_POLICY, estimate_tokens_from_text
from token_estimator import estimate_tokens, estimate_cost, simulate_task, simulate_27m_scenario, simulate_27m_governed
from delegation_handoff import (
    build_handoff, build_followup_handoff, validate_handoff_size,
    fingerprint_handoff, DEFAULT_DELEGATION_CONTEXT_LIMIT, MAX_DELEGATION_CONTEXT_LIMIT,
)


# ── Token Budget Manager Tests ──────────────────────────────────

class TestTokenBudgetManager(unittest.TestCase):

    def setUp(self):
        self.budget = TokenBudgetManager(task_id="test-task-001")

    def test_initial_state(self):
        self.assertEqual(self.budget.total_tokens, 0)
        self.assertEqual(self.budget.model_calls, 0)
        self.assertEqual(self.budget.subagent_calls, 0)
        self.assertFalse(self.budget.warning_triggered)
        self.assertFalse(self.budget.hard_stop_triggered)

    def test_record_accepted_within_budget(self):
        accepted, reason = self.budget.record_request(
            agent="heidi", strategy="direct",
            input_tokens=5000, output_tokens=500,
        )
        self.assertTrue(accepted)
        self.assertEqual(reason, "accepted")
        self.assertEqual(self.budget.total_tokens, 5500)

    def test_record_rejects_exceeding_per_request_input_limit(self):
        accepted, reason = self.budget.record_request(
            agent="heidi", strategy="direct",
            input_tokens=200000, output_tokens=500,
        )
        self.assertFalse(accepted)
        self.assertIn("per-request limit", reason)

    def test_record_rejects_exceeding_per_request_output_limit(self):
        accepted, reason = self.budget.record_request(
            agent="heidi", strategy="direct",
            input_tokens=5000, output_tokens=10000,
        )
        self.assertFalse(accepted)
        self.assertIn("per-request limit", reason)

    def test_record_rejects_exceeding_total_budget(self):
        # Fill budget to near limit
        self.budget.total_tokens = self.budget.policy["max_total_tokens"] - 1000
        accepted, reason = self.budget.record_request(
            agent="heidi", strategy="direct",
            input_tokens=5000, output_tokens=500,
        )
        self.assertFalse(accepted)
        self.assertIn("hard_stop", reason)
        self.assertTrue(self.budget.hard_stop_triggered)

    def test_warning_threshold(self):
        policy = dict(self.budget.policy)
        policy["max_total_tokens"] = 10000
        policy["warning_percent"] = 70
        budget = TokenBudgetManager(policy=policy, task_id="test-warn")
        # Use 60% - should not trigger warning
        # Set accumulators directly so total_tokens reflects the state
        budget.total_input_tokens = 6000
        budget.total_tokens = 6000
        accepted, _ = budget.record_request(agent="heidi", strategy="direct",
                                            input_tokens=500, output_tokens=50)
        self.assertTrue(accepted)
        self.assertFalse(budget.warning_triggered)

        # Now push past 70% (7000)
        accepted, _ = budget.record_request(agent="heidi", strategy="direct",
                                            input_tokens=1500, output_tokens=50)
        self.assertTrue(budget.warning_triggered)

    def test_max_model_calls(self):
        policy = dict(self.budget.policy)
        policy["max_model_calls"] = 2
        budget = TokenBudgetManager(policy=policy, task_id="test-max-calls")
        for i in range(2):
            accepted, _ = budget.record_request(agent="heidi", strategy="direct",
                                                input_tokens=100, output_tokens=10)
            self.assertTrue(accepted)
        # Third call should be rejected (model_calls is now at max)
        accepted, reason = budget.record_request(agent="heidi", strategy="direct",
                                                  input_tokens=100, output_tokens=10)
        self.assertFalse(accepted)
        self.assertIn("model calls", reason)

    def test_max_calls_per_agent(self):
        policy = dict(self.budget.policy)
        policy["max_calls_per_agent"] = 2
        budget = TokenBudgetManager(policy=policy, task_id="test-per-agent")
        for i in range(2):
            accepted, _ = budget.record_request(agent="frontend", strategy="direct",
                                                input_tokens=100, output_tokens=10)
            self.assertTrue(accepted)
        accepted, reason = budget.record_request(agent="frontend", strategy="direct",
                                                  input_tokens=100, output_tokens=10)
        self.assertFalse(accepted)
        self.assertIn("exceeds max", reason)

    def test_max_subagent_calls(self):
        policy = dict(self.budget.policy)
        policy["max_subagent_calls"] = 2
        budget = TokenBudgetManager(policy=policy, task_id="test-subagent")
        for i in range(2):
            accepted, _ = budget.record_request(agent="scout", strategy="scout_then_execute",
                                                input_tokens=100, output_tokens=10)
            self.assertTrue(accepted)
        accepted, reason = budget.record_request(agent="scout", strategy="scout_then_execute",
                                                  input_tokens=100, output_tokens=10)
        self.assertFalse(accepted)
        self.assertIn("at max", reason)

    def test_audit_cycle_limit(self):
        self.budget.record_audit_cycle()
        self.assertEqual(self.budget.audit_cycles, 1)
        allowed = self.budget.record_audit_cycle()
        self.assertFalse(allowed)

    def test_retry_dedup(self):
        fp = "abc123def456"
        allowed, reason = self.budget.check_retry(fp)
        self.assertTrue(allowed)
        allowed, reason = self.budget.check_retry(fp)
        self.assertTrue(allowed)
        allowed, reason = self.budget.check_retry(fp)
        self.assertFalse(allowed)
        self.assertIn("circuit_breaker", reason)

    def test_delegation_blocked_after_warning(self):
        policy = dict(self.budget.policy)
        policy["max_total_tokens"] = 10000
        policy["warning_percent"] = 70
        budget = TokenBudgetManager(policy=policy, task_id="test-delegation")
        budget.total_tokens = 7001
        budget.warning_triggered = True
        self.assertFalse(budget.check_delegation_allowed())

    def test_partial_completion_report(self):
        self.budget.record_request(agent="heidi", strategy="direct",
                                   input_tokens=1000, output_tokens=100)
        self.budget.total_tokens = 1500001
        self.budget.hard_stop_triggered = True
        report = self.budget.get_partial_completion_report()
        self.assertEqual(report["status"], "partial_completion")
        self.assertIn("limit", report["reason"])
        self.assertIsNotNone(report["largest_request"])

    def test_no_double_counting(self):
        self.budget.record_request(agent="heidi", strategy="direct",
                                   input_tokens=1000, output_tokens=100)
        before = self.budget.total_tokens
        # Recording the same request again should not happen in practice,
        # but verify the budget doesn't auto-reset
        self.budget.record_request(agent="heidi", strategy="direct",
                                   input_tokens=1000, output_tokens=100)
        self.assertEqual(self.budget.total_tokens, before + 1100)

    def test_conservative_estimate_without_metadata(self):
        """When tokens are not provided, use conservative text-based estimate."""
        accepted, reason = self.budget.record_request(
            agent="heidi", strategy="direct",
            input_tokens=None, output_tokens=None,
            request_dict={"prompt": "x" * 1000},
        )
        self.assertTrue(accepted)
        # Should have estimated tokens from the request dict
        self.assertGreater(self.budget.total_tokens, 0)

    def test_save_and_load(self):
        self.budget.record_request(agent="heidi", strategy="direct",
                                   input_tokens=1000, output_tokens=100)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            self.budget.save(path)
            new_budget = TokenBudgetManager(task_id="test-task-001")
            new_budget.load(path)
            self.assertEqual(new_budget.total_tokens, self.budget.total_tokens)
            self.assertEqual(new_budget.model_calls, self.budget.model_calls)
        finally:
            os.unlink(path)


# ── Token Estimator Tests ────────────────────────────────────────

class TestTokenEstimator(unittest.TestCase):

    def test_estimate_basic(self):
        result = estimate_tokens(
            system_prompt="You are an assistant.",
            history_messages=5,
            context_chars=1000,
            output_chars=200,
        )
        self.assertGreater(result["total"], 0)
        self.assertIn("uncached_input", result)
        self.assertIn("cached_input", result)
        self.assertIn("output", result)
        self.assertIn("breakdown", result)

    def test_estimate_cached_vs_uncached(self):
        uncached = estimate_tokens(
            context_chars=5000, cached_input_chars=0, cache_write_chars=5000,
        )
        cached = estimate_tokens(
            context_chars=5000, cached_input_chars=5000, cache_write_chars=0,
        )
        # Cached input should be cheaper than uncached
        self.assertGreater(uncached["total"], cached["total"])

    def test_estimate_with_reasoning(self):
        result = estimate_tokens(
            reasoning_chars=500,
        )
        self.assertGreater(result["reasoning"], 0)

    def test_simulate_task(self):
        result = simulate_task(tokens_per_step=5000, steps=10, model="gpt-4o")
        self.assertGreater(result["total_tokens"], 0)
        self.assertEqual(result["total_steps"], 10)
        self.assertIn("estimated_cost_usd", result)

    def test_simulate_27m_scenario(self):
        result = simulate_27m_scenario()
        # The 27M scenario should produce a large token count
        self.assertGreater(result["total_tokens"], 1_000_000)
        self.assertIn("scout_full_context", result["breakdown"])
        self.assertIn("auditor_full_context", result["breakdown"])
        self.assertIn("second_audit_cycle", result["breakdown"])

    def test_simulate_27m_governed(self):
        """Governed scenario should be smaller than unbounded by >80%."""
        governed = simulate_27m_governed()
        unbounded = simulate_27m_scenario()
        self.assertLess(governed["total_tokens"], unbounded["total_tokens"] * 0.2)
        self.assertGreater(governed["model_calls"], 0)
        self.assertGreater(governed["subagent_calls"], 0)
        self.assertIn("budget_warning_triggered", governed)
        self.assertIn("hard_stop_triggered", governed)
        self.assertIn("policy_limits", governed)

    def test_estimate_cost_known_model(self):
        est = estimate_tokens(output_chars=1000, model="gpt-4o")
        cost = estimate_cost(est, "gpt-4o")
        self.assertIsNotNone(cost)
        self.assertGreater(cost["estimated_cost_usd"], 0)

    def test_estimate_cost_unknown_model(self):
        est = estimate_tokens(output_chars=1000)
        cost = estimate_cost(est, "unknown-model")
        self.assertIsNone(cost)


# ── Delegation Handoff Tests ─────────────────────────────────────

class TestDelegationHandoff(unittest.TestCase):

    def test_compact_handoff(self):
        handoff = build_handoff(
            task_objective="Fix login bug",
            agent="debugger",
            owned_files=["src/auth/login.py"],
            shared_files=["src/auth/session.py"],
            constraints=["No auth changes without security review"],
            evidence=["Test failure at test_login.py:42"],
            acceptance_checks=["Login test passes", "No regression in session tests"],
        )
        valid, tokens, limit = validate_handoff_size(handoff)
        self.assertTrue(valid, f"Handoff exceeded limit: {tokens} > {limit}")
        self.assertNotIn("conversation_history", handoff)
        self.assertNotIn("full_scout_report", handoff)

    def test_handoff_excludes_unrelated_history(self):
        handoff = build_handoff(
            task_objective="Add button",
            agent="frontend",
        )
        # Should not contain conversation history or full context
        self.assertNotIn("conversation_history", handoff)
        self.assertNotIn("full_context", handoff)
        self.assertNotIn("terminal_logs", handoff)

    def test_followup_handoff_is_delta_only(self):
        prev = build_handoff(
            task_objective="Fix login bug",
            agent="debugger",
            owned_files=["src/auth/login.py"],
        )
        followup = build_followup_handoff(
            previous_handoff=prev,
            new_failure="Test still fails with same error",
            changed_files=["src/auth/login.py"],
            remaining_issue="Root cause not yet identified",
            required_correction="Try different hypothesis",
        )
        self.assertIn("new_failure", followup)
        self.assertIn("changed_files", followup)
        self.assertIn("remaining_issue", followup)
        self.assertIn("required_correction", followup)
        # Should not include full previous handoff content
        self.assertNotIn("owned_files", followup)

    def test_handoff_size_limit(self):
        handoff = build_handoff(
            task_objective="X" * 10000,  # very long objective
            agent="heidi",
            context_limit=1500,
        )
        valid, tokens, limit = validate_handoff_size(handoff, limit=1500)
        # After aggressive truncation, should be within limit
        self.assertTrue(valid, f"Handoff {tokens} tokens exceeds {limit}")

    def test_handoff_fingerprint_stable(self):
        handoff1 = build_handoff(task_objective="Fix bug", agent="debugger")
        handoff2 = build_handoff(task_objective="Fix bug", agent="debugger")
        fp1 = fingerprint_handoff(handoff1)
        fp2 = fingerprint_handoff(handoff2)
        self.assertEqual(fp1, fp2)

    def test_delegation_context_limit_default(self):
        self.assertEqual(DEFAULT_DELEGATION_CONTEXT_LIMIT, 1500)

    def test_delegation_context_limit_max(self):
        self.assertEqual(MAX_DELEGATION_CONTEXT_LIMIT, 4000)

    def test_handoff_with_remaining_budget(self):
        handoff = build_handoff(
            task_objective="Fix bug",
            agent="debugger",
            remaining_budget={"tokens_remaining": 50000, "calls_remaining": 5},
        )
        self.assertIn("remaining_budget", handoff)
        self.assertEqual(handoff["remaining_budget"]["tokens_remaining"], 50000)


# ── Context Memory Budget Enforcement Tests ──────────────────────
# These are in test_context_memory.py


if __name__ == "__main__":
    unittest.main()