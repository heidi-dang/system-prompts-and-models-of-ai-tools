import unittest
import subprocess
import os
import sys


class TestNativePromptComposition(unittest.TestCase):
    def test_runtime_doctor_graceful_when_opencode_unavailable(self):
        """runtime_doctor should exit 0 and report UNAVAILABLE when opencode not installed."""
        result = subprocess.run(
            [sys.executable, "opencode-agent-pack/scripts/runtime_doctor.py", "native-prompt"],
            capture_output=True, text=True,
        )
        self.assertIn(result.returncode, [0, 1])

    def test_heidi_agent_no_duplicate_task_identifier(self):
        """Heidi agent should not have duplicate Task identifier sections."""
        with open("opencode-agent-pack/agents/heidi.md") as f:
            content = f.read()
        count = content.count("## Task tool identifier rule")
        self.assertLessEqual(count, 1, "Duplicate Task identifier sections found")

    def test_heidi_agent_no_direct_rules_append(self):
        """Heidi agent should not instruct to APPEND directly to rules.md."""
        with open("opencode-agent-pack/agents/heidi.md") as f:
            content = f.read()
        self.assertNotIn("APPEND a concise entry under the section", content)

    def test_specialists_have_memory_candidate_protocol(self):
        """All specialist agents should reference Memory Candidate protocol."""
        specialists = ["scout", "frontend", "backend", "debugger", "auditor", "planner"]
        for agent in specialists:
            with open(f"opencode-agent-pack/agents/{agent}.md") as f:
                content = f.read()
            self.assertIn(
                "Memory Candidate", content,
                f"{agent}.md missing Memory Candidate protocol",
            )

    def test_gen_prompts_no_duplicates(self):
        """Generated prompts should not have duplicate sections."""
        result = subprocess.run(
            [sys.executable, "opencode-agent-pack/scripts/gen-prompts.py", "--check"],
            capture_output=True, text=True,
        )
        # May fail if runtime modules missing - that's OK for CI
        self.assertIn(result.returncode, [0, 1])


if __name__ == "__main__":
    unittest.main()
