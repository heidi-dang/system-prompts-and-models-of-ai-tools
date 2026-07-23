#!/usr/bin/env python3
"""Tests for proactive_audit.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "opencode-agent-pack", "scripts", "proactive_audit.py")

def run(*args):
    proc = subprocess.run([sys.executable, SCRIPT] + list(args), capture_output=True, text=True, timeout=30)
    return proc.returncode, proc.stdout.strip(), proc.stderr

class TestProactiveAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make_repo(self):
        (self.tmp / "tests").mkdir(exist_ok=True)
        (self.tmp / ".heidi").mkdir(exist_ok=True)
        (self.tmp / ".heidi" / "rules.md").write_text("# Rules\n")
        (self.tmp / ".heidi" / "commands.md").write_text("# Commands\n")
        (self.tmp / ".heidi" / "context-index.json").write_text('{"schema_version":"2.0.0","files":[]}')
        (self.tmp / ".heidi" / "memory.jsonl").write_text("")
        return self.tmp

    def test_clean_scores_high(self):
        root = self.make_repo()
        rc, out, _ = run("--root", str(root))
        self.assertIn("Score:", out)

    def test_missing_context_reported(self):
        root = self.make_repo()
        (root / ".heidi" / "context-index.json").unlink()
        rc, out, _ = run("--root", str(root))
        self.assertIn("stale_context_index", out)

    def test_report_created(self):
        root = self.make_repo()
        out_path = self.tmp / "report.md"
        rc, _, _ = run("--root", str(root), "--out", str(out_path))
        self.assertEqual(rc, 0)
        self.assertTrue(out_path.exists())

    def test_report_format_stable(self):
        root = self.make_repo()
        rc, out, _ = run("--root", str(root))
        self.assertIn("## Summary", out)
        self.assertIn("## Findings", out)
        self.assertIn("## Suggested Next Actions", out)


if __name__ == "__main__":
    unittest.main()
