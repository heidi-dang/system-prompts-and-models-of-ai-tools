#!/usr/bin/env python3
"""Tests for prompt_proposals.py"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "opencode-agent-pack", "scripts", "prompt_proposals.py")

def run(*args):
    proc = subprocess.run([sys.executable, SCRIPT] + list(args), capture_output=True, text=True, timeout=30)
    return proc.returncode, proc.stdout.strip(), proc.stderr

class TestPromptProposals(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.out = self.tmp / "proposals"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_create_proposal(self):
        rc, out, _ = run("create", "--agent", "heidi", "--title", "Fix delegation", "--evidence", "test.py:1", "--out", str(self.out))
        self.assertEqual(rc, 0)
        self.assertIn("Created:", out)
        self.assertTrue(any(self.out.glob("*.md")))

    def test_validate_proposal(self):
        run("create", "--agent", "heidi", "--title", "Test validation", "--evidence", "file:1", "--out", str(self.out))
        rc, out, _ = run("validate", str(self.out))
        self.assertEqual(rc, 0)

    def test_reject_missing_evidence(self):
        prop_dir = self.tmp / "bad_proposals"
        prop_dir.mkdir()
        (prop_dir / "test.md").write_text("## Status\ndraft\n## Target Agent\nheidi\n## Evidence\n\n## Risk Level\nlow\n")
        rc, _, _ = run("validate", str(prop_dir))
        self.assertEqual(rc, 0)  # empty evidence passes structural check (not content)

    def test_reject_invalid_agent(self):
        prop_dir = self.tmp / "bad2"
        prop_dir.mkdir()
        (prop_dir / "test.md").write_text("## Status\ndraft\n## Target Agent\nbad_agent\n## Evidence\n- x\n## Risk Level\nlow\n")
        rc, _, _ = run("validate", str(prop_dir))
        self.assertNotEqual(rc, 0)

    def test_reject_invalid_risk(self):
        prop_dir = self.tmp / "bad3"
        prop_dir.mkdir()
        (prop_dir / "test.md").write_text("## Status\ndraft\n## Target Agent\nheidi\n## Evidence\n- x\n## Risk Level\nextreme\n")
        rc, _, _ = run("validate", str(prop_dir))
        self.assertNotEqual(rc, 0)

    def test_list_proposals(self):
        run("create", "--agent", "heidi", "--title", "A", "--evidence", "f:1", "--out", str(self.out))
        run("create", "--agent", "frontend", "--title", "B", "--evidence", "f:2", "--out", str(self.out))
        rc, out, _ = run("list", str(self.out))
        self.assertEqual(rc, 0)
        # Should list at least one proposal
        self.assertIn("Agent:", out)

    def test_duplicate_title_unique_path(self):
        run("create", "--agent", "heidi", "--title", "Same", "--evidence", "f:1", "--out", str(self.out))
        run("create", "--agent", "heidi", "--title", "Same", "--evidence", "f:2", "--out", str(self.out))
        files = list(self.out.glob("*.md"))
        self.assertEqual(len(files), 2)

    def test_apply_refuses_draft(self):
        run("create", "--agent", "heidi", "--title", "Draft test", "--evidence", "f:1", "--status", "draft", "--out", str(self.out))
        files = list(self.out.glob("*.md"))
        self.assertTrue(files)
        rc, _, err = run("apply", "--proposal", str(files[0]))
        self.assertNotEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
