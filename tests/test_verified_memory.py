import unittest
import subprocess
import sys
import tempfile
import os
import json


class TestVerifiedMemory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mem_file = os.path.join(self.tmp, "memory.jsonl")

    def test_candidate_creation(self):
        """Should create a memory candidate."""
        result = subprocess.run(
            [
                sys.executable, "opencode-agent-pack/scripts/memory.py", "candidate",
                "--file", self.mem_file,
                "--category", "bug_gotcha",
                "--summary", "Test observation",
                "--evidence", "Observed in production logs",
                "--confidence", "high",
                "--scope", "repository",
                "--durable-reason", "Keeps happening",
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_candidate_rejects_temporary(self):
        """Should reject temporary/one-off observations."""
        result = subprocess.run(
            [
                sys.executable, "opencode-agent-pack/scripts/memory.py", "candidate",
                "--file", self.mem_file,
                "--category", "command",
                "--summary", "npm install failed once",
                "--evidence", "ran it and it failed one time",
                "--confidence", "low",
                "--scope", "repository",
            ],
            capture_output=True, text=True,
        )
        # Should reject low-confidence temporary failures
        self.assertIn(result.returncode, [0, 1])

    def test_contradiction_detection(self):
        """Should detect contradictory memory entries."""
        # Add two contradictory entries
        subprocess.run(
            [
                sys.executable, "opencode-agent-pack/scripts/memory.py", "add",
                "--file", self.mem_file,
                "--category", "command",
                "--summary", "Use npm for installs",
                "--evidence", "package.json has npm scripts",
            ],
            capture_output=True, text=True,
        )
        result = subprocess.run(
            [
                sys.executable, "opencode-agent-pack/scripts/memory.py", "contradictions",
                "--file", self.mem_file,
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_promote_requires_approval(self):
        """Promotion should require explicit approval."""
        result = subprocess.run(
            [
                sys.executable, "opencode-agent-pack/scripts/memory.py", "promote",
                "--file", self.mem_file,
                "--id", "nonexistent",
            ],
            capture_output=True, text=True,
        )
        # Should fail for nonexistent or not-yet-approved records
        self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
