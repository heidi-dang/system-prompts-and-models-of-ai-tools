#!/usr/bin/env python3
"""Regenerate prompt-only files from agent markdown (strip frontmatter)."""
import os
import re
from pathlib import Path

AGENTS_DIR = "opencode-agent-pack/agents"
PROMPTS_DIR = "opencode-agent-pack/prompts"
AGENT_NAMES = ["heidi", "frontend", "backend", "debugger", "auditor", "planner", "scout"]

os.makedirs(PROMPTS_DIR, exist_ok=True)
for name in AGENT_NAMES:
    src = Path(AGENTS_DIR) / f"{name}.md"
    dst = Path(PROMPTS_DIR) / f"{name}.prompt.md"
    if not src.exists():
        print(f"WARNING: {src} not found")
        continue
    content = src.read_text(encoding="utf-8")
    # Strip YAML frontmatter
    content = re.sub(r'^---\n.*?\n---\n', '', content, count=1, flags=re.DOTALL).lstrip("\n")
    dst.write_text(content, encoding="utf-8")
    print(f"Generated: {dst}")
