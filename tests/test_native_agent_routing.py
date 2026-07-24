import unittest
import subprocess
import sys


class TestNativeAgentRouting(unittest.TestCase):
    def test_explore_in_heidi_task_list(self):
        """Heidi's allowlist should include explore."""
        with open("opencode-agent-pack/agents/heidi.md") as f:
            content = f.read()
        self.assertIn("explore: allow", content)

    def test_general_in_heidi_task_list(self):
        """Heidi's allowlist should include general."""
        with open("opencode-agent-pack/agents/heidi.md") as f:
            content = f.read()
        self.assertIn("general: allow", content)

    def test_specialists_deny_task(self):
        """All specialists should deny task delegation."""
        specialists = ["scout", "frontend", "backend", "debugger", "auditor", "planner"]
        for agent in specialists:
            with open(f"opencode-agent-pack/agents/{agent}.md") as f:
                content = f.read()
            # Specialists should not have task: allow blocks
            if "task:" in content[:200]:
                task_block = content[content.index("task:"):content.index("task:") + 200]
                self.assertIn(
                    "deny", task_block,
                    f"{agent}.md should deny task delegation",
                )


if __name__ == "__main__":
    unittest.main()
