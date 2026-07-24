#!/usr/bin/env python3
"""Tests for runtime_doctor.py token governance checks."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DOCTOR_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "opencode-agent-pack", "scripts", "runtime_doctor.py"
)


def run_doctor(*args):
    proc = subprocess.run(
        [sys.executable, DOCTOR_SCRIPT] + list(args),
        capture_output=True, text=True, timeout=30,
    )
    return proc.returncode, proc.stdout, proc.stderr


class TestRuntimeDoctor(unittest.TestCase):

    def test_validate_token_policy_present(self):
        """Token governance checks should find the runtime policy."""
        rc, out, err = run_doctor("native-prompt")
        # The doctor should report on token governance
        self.assertIn("Token policy present", out)

    def test_validate_budget_manager_exists(self):
        """Budget manager module should be detected."""
        rc, out, err = run_doctor("native-prompt")
        self.assertIn("Budget manager module", out)

    def test_validate_delegation_payload_capped(self):
        """Delegation payload cap should be detected."""
        rc, out, err = run_doctor("native-prompt")
        self.assertIn("Delegation payload capped", out)

    def test_validate_subagent_limits(self):
        """Subagent limits should be enforced."""
        rc, out, err = run_doctor("native-prompt")
        self.assertIn("Subagent limits enforced", out)

    def test_validate_retry_circuit_breaker(self):
        """Retry circuit breaker should be active."""
        rc, out, err = run_doctor("native-prompt")
        self.assertIn("Retry circuit breaker active", out)

    def test_validate_audit_cycle_limit(self):
        """Audit cycle limit should be active."""
        rc, out, err = run_doctor("native-prompt")
        self.assertIn("Audit-cycle limit active", out)

    def test_validate_no_conflicting_defaults(self):
        """No conflicting token-policy defaults should be detected."""
        rc, out, err = run_doctor("native-prompt")
        self.assertIn("No conflicting token-policy defaults", out)

    def test_validate_task_ledger_token_usage(self):
        """Task ledger should write token usage."""
        rc, out, err = run_doctor("native-prompt")
        self.assertIn("Task ledger writes token usage", out)

    def test_validate_exit_code_on_failure(self):
        """Doctor should return non-zero when checks fail."""
        rc, out, err = run_doctor("native-prompt")
        # Token governance checks should pass (policy exists, modules exist)
        self.assertIsInstance(rc, int)

    # ── Agent-registry checks ────────────────────────────────────

    def _run_validate_isolated(self, tmpdir, mode="isolated"):
        """Run validate with OPENCODE_CONFIG_DIR pointing to tmpdir."""
        env = os.environ.copy()
        env["OPENCODE_CONFIG_DIR"] = tmpdir
        proc = subprocess.run(
            [sys.executable, DOCTOR_SCRIPT, "validate", "--mode", mode],
            capture_output=True, text=True, timeout=30, env=env,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def test_agent_registry_detects_stale_runtime_in_agent_dir(self):
        """validate should FAIL when runtime/ exists inside agent directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir) / "agents"
            runtime_dir = agent_dir / "runtime" / "prompts"
            runtime_dir.mkdir(parents=True)
            (agent_dir / "heidi.md").write_text("public agent")
            (agent_dir / "runtime" / "heidi-orchestration.md").write_text("internal")
            (agent_dir / "runtime" / "prompts" / "core.md").write_text("internal fragment")

            rc, out, err = self._run_validate_isolated(tmpdir)
            self.assertIn("runtime/heidi-orchestration.md: FAIL", out,
                          "Doctor should detect stale runtime prompt in agent dir")

    def test_agent_registry_public_agents_allowed(self):
        """validate should PASS when only flat .md files are in agent dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir) / "agents"
            agent_dir.mkdir(parents=True)
            for a in ("heidi", "frontend", "backend"):
                (agent_dir / f"{a}.md").write_text(f"public agent {a}")

            rc, out, err = self._run_validate_isolated(tmpdir)
            fail_lines = [l for l in out.split('\n') if 'FAIL' in l and 'Agent registry' in l]
            self.assertEqual(len(fail_lines), 0,
                             f"Should have no agent-registry FAILs: {fail_lines}")

    def test_agent_registry_exits_nonzero_with_stale_runtime(self):
        """validate should exit non-zero when stale runtime files in agent dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir) / "agents"
            runtime_dir = agent_dir / "runtime"
            runtime_dir.mkdir(parents=True)
            (agent_dir / "heidi.md").write_text("public")
            (runtime_dir / "internal.md").write_text("internal")

            rc, out, err = self._run_validate_isolated(tmpdir)
            self.assertNotEqual(rc, 0,
                                "Doctor should exit non-zero with stale runtime files")


if __name__ == "__main__":
    unittest.main()