import unittest
import subprocess
import sys


class TestFastPath(unittest.TestCase):
    def test_simple_edit_is_fast_path(self):
        """A simple typo fix should qualify for fast path."""
        result = subprocess.run(
            [
                sys.executable, "opencode-agent-pack/scripts/strategy_selector.py",
                "fast-path-check", "--task", "fix typo in README",
            ],
            capture_output=True, text=True,
        )
        self.assertIn(result.returncode, [0, 1])

    def test_auth_change_not_fast_path(self):
        """An auth change should not qualify for fast path."""
        result = subprocess.run(
            [
                sys.executable, "opencode-agent-pack/scripts/strategy_selector.py",
                "fast-path-check", "--task", "add authentication to the login endpoint",
            ],
            capture_output=True, text=True,
        )
        self.assertIn(result.returncode, [0, 1])

    def test_migration_not_fast_path(self):
        """A database migration should not qualify for fast path."""
        result = subprocess.run(
            [
                sys.executable, "opencode-agent-pack/scripts/strategy_selector.py",
                "fast-path-check", "--task", "create database migration for users table",
            ],
            capture_output=True, text=True,
        )
        self.assertIn(result.returncode, [0, 1])

    def test_multi_domain_not_fast_path(self):
        """A multi-domain feature should not qualify for fast path."""
        result = subprocess.run(
            [
                sys.executable, "opencode-agent-pack/scripts/strategy_selector.py",
                "fast-path-check", "--task", "build a user dashboard with frontend UI and backend API",
            ],
            capture_output=True, text=True,
        )
        self.assertIn(result.returncode, [0, 1])

    def test_failing_ci_not_fast_path(self):
        """A failing CI investigation should not qualify for fast path."""
        result = subprocess.run(
            [
                sys.executable, "opencode-agent-pack/scripts/strategy_selector.py",
                "fast-path-check", "--task", "CI is failing with type error in build step",
            ],
            capture_output=True, text=True,
        )
        self.assertIn(result.returncode, [0, 1])


if __name__ == "__main__":
    unittest.main()
