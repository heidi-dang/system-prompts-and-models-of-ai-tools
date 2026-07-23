#!/usr/bin/env python3
"""Tests for memory.py utility."""
import os
import sys
import json
import tempfile
import unittest
import subprocess

MEMORY_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "opencode-agent-pack", "scripts", "memory.py")


def run(*args, input_data=None):
    """Run memory.py with args, return (returncode, stdout, stderr)."""
    cmd = [sys.executable, MEMORY_SCRIPT] + list(args)
    proc = subprocess.run(
        cmd,
        input=input_data,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.returncode, proc.stdout, proc.stderr


class TestMemory(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_empty_validates(self):
        rc, out, err = run("validate", self.path)
        self.assertEqual(rc, 0, f"stderr: {err}")

    def test_add_record(self):
        rc, out, err = run(
            "add",
            "--file", self.path,
            "--category", "bug_gotcha",
            "--summary", "Fixed race condition in cache",
            "--evidence", "src/cache.rs:142",
            "--confidence", "high",
        )
        self.assertEqual(rc, 0, f"stderr: {err}")
        self.assertIn("Added:", out)

    def test_stable_id_deterministic(self):
        rc1, out1, _ = run("add", "--file", self.path, "--category", "architecture",
                           "--summary", "Use PostgreSQL", "--evidence", "prd.md:5",
                           "--confidence", "high")
        first_id = out1.strip().split(": ")[-1]
        rc2, out2, _ = run("add", "--file", self.path, "--category", "architecture",
                           "--summary", "Use PostgreSQL", "--evidence", "prd.md:5",
                           "--confidence", "high")
        self.assertEqual(rc2, 0)
        self.assertIn("Skipped (duplicate)", out2)

    def test_duplicate_skipped(self):
        run("add", "--file", self.path, "--category", "command",
            "--summary", "npm test", "--evidence", "package.json:10")
        rc, out, _ = run("add", "--file", self.path, "--category", "command",
                         "--summary", "npm test", "--evidence", "package.json:10")
        self.assertIn("Skipped", out)

    def test_invalid_json_rejected(self):
        with open(self.path, "w") as f:
            f.write("not valid json\n")
        rc, out, err = run("validate", self.path)
        self.assertNotEqual(rc, 0)

    def test_missing_evidence_rejected(self):
        # Write directly - add command requires evidence
        with open(self.path, "w") as f:
            json.dump({"id": "bad", "category": "workflow", "summary": "no evidence",
                       "evidence": [], "confidence": "high"}, f)
            f.write("\n")
        rc, out, err = run("validate", self.path)
        self.assertNotEqual(rc, 0)

    def test_unsupported_category_rejected(self):
        record = {"id": "bad", "created_at": "now", "category": "unknown",
                  "summary": "bad", "evidence": ["file:1"], "confidence": "high"}
        with open(self.path, "w") as f:
            f.write(json.dumps(record) + "\n")
        rc, out, err = run("validate", self.path)
        self.assertNotEqual(rc, 0)

    def test_unsupported_confidence_rejected(self):
        record = {"id": "bad2", "created_at": "now", "category": "workflow",
                  "summary": "test", "evidence": ["file:1"], "confidence": "extreme"}
        with open(self.path, "w") as f:
            f.write(json.dumps(record) + "\n")
        rc, out, err = run("validate", self.path)
        self.assertNotEqual(rc, 0)

    def test_existing_entries_preserved(self):
        run("add", "--file", self.path, "--category", "architecture",
            "--summary", "Microservices", "--evidence", "arch.md:1")
        rc, out, _ = run("list", "--file", self.path)
        self.assertEqual(rc, 0)
        self.assertIn("Microservices", out)

    def test_list_output(self):
        run("add", "--file", self.path, "--category", "workflow",
            "--summary", "Deploy on Fridays", "--evidence", "ops.md:3")
        rc, out, _ = run("list", "--file", self.path)
        self.assertEqual(rc, 0)
        self.assertIn("Deploy on Fridays", out)
        self.assertIn("ops.md:3", out)


if __name__ == "__main__":
    unittest.main()
