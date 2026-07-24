import unittest
import subprocess
import sys
import json


class TestBenchmark(unittest.TestCase):
    def test_validate_schema(self):
        """Benchmark validate should find the schema."""
        result = subprocess.run(
            [sys.executable, "opencode-agent-pack/scripts/benchmark.py", "validate"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_tasks_have_valid_configs(self):
        """All benchmark task configs should be valid JSON."""
        import glob
        for config_file in glob.glob("benchmarks/tasks/*/config.json"):
            with open(config_file) as f:
                config = json.load(f)
            self.assertIn("task_id", config)
            self.assertIn("task_category", config)
            self.assertIn("request", config)

    def test_grader_works(self):
        """Grader should produce valid scores."""
        # Create a mock result
        mock_result = json.dumps({
            "task_completed": True,
            "files_changed": ["README.md"],
            "files_created": 0,
            "tests_passed": [],
            "retries": 0,
            "elapsed_time": 5.2,
            "tool_calls": 3,
            "token_usage": None,
            "audit_findings": 0,
            "repository_cleanliness": "clean",
            "result_reproducible": True,
        })
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(mock_result)
            result_path = f.name
        try:
            result = subprocess.run(
                [
                    sys.executable, "benchmarks/graders/grade.py", "grade",
                    "--task", "benchmarks/tasks/fast-one-line-edit/config.json",
                    "--result", result_path,
                ],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0)
            grade = json.loads(result.stdout)
            self.assertIn("score", grade)
        finally:
            os.unlink(result_path)

    def test_no_fabricated_benchmark_numbers(self):
        """Benchmark script should not contain fabricated results."""
        with open("opencode-agent-pack/scripts/benchmark.py") as f:
            content = f.read()
        self.assertIn("null", content.lower())
        # Should not hardcode specific scores for real models
        hardcoded_scores = [
            s for s in ["score: 100", "score: 95", "score: 90"]
            if s in content.lower()
        ]
        self.assertEqual(
            len(hardcoded_scores), 0,
            "Should not hardcode benchmark scores",
        )


if __name__ == "__main__":
    unittest.main()
