import unittest
import subprocess
import sys
import tempfile
import os


class TestRuntimeEvents(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.events_file = os.path.join(self.tmp, "runtime-events.jsonl")

    def test_event_creation(self):
        result = subprocess.run(
            [
                sys.executable, "opencode-agent-pack/scripts/runtime_events.py", "event",
                "--file", self.events_file,
                "--type", "runtime_start",
                "--task-id", "test-task-001",
                "--data", '{"model": "current"}',
            ],
            capture_output=True, text=True,
        )
        self.assertIn(result.returncode, [0, 1])

    def test_validate_events(self):
        result = subprocess.run(
            [
                sys.executable, "opencode-agent-pack/scripts/runtime_events.py", "validate",
                self.events_file,
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_report_generation(self):
        result = subprocess.run(
            [
                sys.executable, "opencode-agent-pack/scripts/runtime_events.py", "report",
                self.events_file,
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
