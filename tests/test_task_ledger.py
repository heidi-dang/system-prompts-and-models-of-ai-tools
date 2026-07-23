#!/usr/bin/env python3
"""Tests for task_ledger.py"""
import json
import os
import shutil
import tempfile
import unittest
import subprocess
import sys
from pathlib import Path

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "opencode-agent-pack", "scripts", "task_ledger.py")

def run(*args):
    proc = subprocess.run([sys.executable, SCRIPT] + list(args), capture_output=True, text=True, timeout=30)
    return proc.returncode, proc.stdout.strip(), proc.stderr


class TestTaskLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.ledger = self.tmp / "ledger.jsonl"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_init_idempotent(self):
        rc, out, _ = run("init", str(self.ledger))
        self.assertEqual(rc, 0)
        self.assertTrue(self.ledger.exists())
        rc2, out2, _ = run("init", str(self.ledger))
        self.assertEqual(rc2, 0)
        self.assertIn("idempotent", out2)

    def test_start_creates_task(self):
        run("init", str(self.ledger))
        rc, out, _ = run("start", "--file", str(self.ledger), "--task-name", "Fix bug")
        self.assertEqual(rc, 0)
        self.assertTrue(len(out) == 16)  # task_id is 16 hex chars

    def test_event_appends_valid_event(self):
        run("init", str(self.ledger))
        _, tid, _ = run("start", "--file", str(self.ledger), "--task-name", "Test")
        _, eid, _ = run("event", "--file", str(self.ledger), "--task-id", tid, "--agent", "debugger", "--type", "test_run", "--summary", "Tests failed", "--status", "fail")
        self.assertEqual(len(eid), 16)

    def test_finish_closes_task(self):
        run("init", str(self.ledger))
        _, tid, _ = run("start", "--file", str(self.ledger), "--task-name", "Finish test")
        rc, _, _ = run("finish", "--file", str(self.ledger), "--task-id", tid, "--status", "done", "--score", "9.5")
        self.assertEqual(rc, 0)

    def test_duplicate_events_not_added(self):
        run("init", str(self.ledger))
        _, tid, _ = run("start", "--file", str(self.ledger), "--task-name", "Dup test")
        run("event", "--file", str(self.ledger), "--task-id", tid, "--agent", "frontend", "--type", "delegation", "--summary", "X", "--status", "info")
        with open(self.ledger) as f:
            count1 = sum(1 for line in f if line.strip())
        run("event", "--file", str(self.ledger), "--task-id", tid, "--agent", "frontend", "--type", "delegation", "--summary", "X", "--status", "info")
        with open(self.ledger) as f:
            count2 = sum(1 for line in f if line.strip())
        self.assertEqual(count1, count2)

    def test_invalid_agent_rejected(self):
        run("init", str(self.ledger))
        _, tid, _ = run("start", "--file", str(self.ledger), "--task-name", "Bad agent")
        rc, _, _ = run("event", "--file", str(self.ledger), "--task-id", tid, "--agent", "not_an_agent", "--type", "test_run", "--summary", "x", "--status", "pass")
        self.assertNotEqual(rc, 0)

    def test_invalid_status_rejected(self):
        run("init", str(self.ledger))
        _, tid, _ = run("start", "--file", str(self.ledger), "--task-name", "Bad status")
        rc, _, _ = run("event", "--file", str(self.ledger), "--task-id", tid, "--agent", "heidi", "--type", "test_run", "--summary", "x", "--status", "badstatus")
        self.assertNotEqual(rc, 0)

    def test_report_aggregates_metrics(self):
        run("init", str(self.ledger))
        _, tid, _ = run("start", "--file", str(self.ledger), "--task-name", "Metrics test")
        run("event", "--file", str(self.ledger), "--task-id", tid, "--agent", "debugger", "--type", "test_run", "--summary", "fail", "--status", "fail", "--attempts", "3")
        run("finish", "--file", str(self.ledger), "--task-id", tid, "--status", "done", "--score", "8")
        rc, out, _ = run("report", "--file", str(self.ledger))
        self.assertIn("Total retries: 2", out)
        self.assertIn("Average score: 8.0", out)

    def test_malformed_jsonl_fails(self):
        self.ledger.write_text("not json\n")
        rc, _, err = run("report", "--file", str(self.ledger))
        self.assertNotEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
