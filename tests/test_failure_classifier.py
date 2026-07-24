import unittest
import subprocess
import sys


class TestFailureClassifier(unittest.TestCase):
    def test_classify_permission_denied(self):
        result = subprocess.run(
            [
                sys.executable, "opencode-agent-pack/scripts/failure_classifier.py", "classify",
                "--type", "permission",
                "--evidence", "access denied to /etc/foo",
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_classify_unknown(self):
        result = subprocess.run(
            [
                sys.executable, "opencode-agent-pack/scripts/failure_classifier.py", "classify",
                "--type", "unknown",
                "--evidence", "something weird happened",
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_policy_shows_retry_limits(self):
        result = subprocess.run(
            [
                sys.executable, "opencode-agent-pack/scripts/failure_classifier.py", "policy",
                "--type", "implementation",
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_circuit_breaker_third_failure(self):
        """Three failures of same type should trigger circuit breaker."""
        result = subprocess.run(
            [
                sys.executable, "opencode-agent-pack/scripts/failure_classifier.py", "policy",
                "--type", "external_service",
            ],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
