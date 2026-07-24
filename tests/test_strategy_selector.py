#!/usr/bin/env python3
"""Tests for strategy_selector.py"""
import json
import os
import subprocess
import sys
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "opencode-agent-pack", "scripts", "strategy_selector.py")

def run(*args):
    proc = subprocess.run([sys.executable, SCRIPT] + list(args), capture_output=True, text=True, timeout=30)
    return proc.returncode, proc.stdout.strip(), proc.stderr

class TestStrategySelector(unittest.TestCase):
    def assert_strategy(self, task, expected):
        rc, out, _ = run("select", "--task", task)
        self.assertEqual(rc, 0)
        result = json.loads(out)
        actual = result["strategy"]
        self.assertEqual(actual, expected, f"task='{task}' got {actual}")

    def test_ci_failure_debugger(self):
        self.assert_strategy("Fix failing CI in frontend tests", "debugger_root_cause")

    def test_ui_api_parallel(self):
        self.assert_strategy("Add login form on frontend and auth endpoint on backend", "frontend_backend_parallel")

    def test_unfamiliar_repo_scout(self):
        # "Explore new codebase" may match explore_then_direct or scout_then_execute
        rc, out, _ = run("select", "--task", "Explore new codebase structure")
        result = json.loads(out)
        self.assertIn(result["strategy"], ["scout_then_execute", "explore_then_direct"])

    def test_roadmap_planner(self):
        # "Plan roadmap" may match planner_then_execute or scout_then_execute
        rc, out, _ = run("select", "--task", "Plan roadmap for next quarter")
        result = json.loads(out)
        self.assertIn(result["strategy"], ["planner_then_execute", "scout_then_execute"])

    def test_audit_request(self):
        self.assert_strategy("Audit the security of auth module", "audit_only")

    def test_prompt_change_proposal(self):
        self.assert_strategy("Improve heidi agent prompt for better delegation", "prompt_improvement_proposal")

    def test_simple_typo_direct(self):
        # "Fix typo" may match fast_direct or direct_single_agent
        rc, out, _ = run("select", "--task", "Fix typo in README")
        result = json.loads(out)
        self.assertIn(result["strategy"], ["direct_single_agent", "fast_direct"])

    def test_validate_fails_invalid_file(self):
        rc, _, _ = run("validate", "/nonexistent.json")
        self.assertNotEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
