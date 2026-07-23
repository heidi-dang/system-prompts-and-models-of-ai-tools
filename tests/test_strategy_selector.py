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
        self.assertEqual(result["strategy"], expected, f"task='{task}' got {result['strategy']}")

    def test_ci_failure_debugger(self):
        self.assert_strategy("Fix failing CI in frontend tests", "debugger_root_cause")

    def test_ui_api_parallel(self):
        self.assert_strategy("Add login form on frontend and auth endpoint on backend", "frontend_backend_parallel")

    def test_unfamiliar_repo_scout(self):
        self.assert_strategy("Explore new codebase structure", "scout_then_execute")

    def test_roadmap_planner(self):
        self.assert_strategy("Plan roadmap for next quarter", "planner_then_execute")

    def test_audit_request(self):
        self.assert_strategy("Audit the security of auth module", "audit_only")

    def test_prompt_change_proposal(self):
        self.assert_strategy("Improve heidi agent prompt for better delegation", "prompt_improvement_proposal")

    def test_simple_typo_direct(self):
        self.assert_strategy("Fix typo in README", "direct_single_agent")

    def test_validate_fails_invalid_file(self):
        rc, _, _ = run("validate", "/nonexistent.json")
        self.assertNotEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
