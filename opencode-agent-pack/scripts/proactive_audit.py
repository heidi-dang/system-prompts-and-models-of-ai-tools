#!/usr/bin/env python3
"""
Proactive Audit Mode — identify issues and suggest fixes without auto-modification.

Commands:
  run --root <r> [--context <f>] [--out <f>]  Run proactive audit
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

CHECKLIST = [
    ("stale_context_index", "high", "Stale or missing context index", lambda root, ctx: not (Path(root) / ".heidi" / "context-index.json").exists()),
    ("missing_rules", "high", "Missing .heidi/rules.md", lambda root, ctx: not (Path(root) / ".heidi" / "rules.md").exists()),
    ("missing_commands", "medium", "Missing verified commands", lambda root, ctx: not (Path(root) / ".heidi" / "commands.md").exists()),
    ("agent_mode", "high", "Agent ':mode' check", lambda root, ctx: check_agent_modes(root)),
    ("deprecated_key", "high", "Deprecated config key check", lambda root, ctx: check_deprecated_key(root)),
    ("missing_ci", "medium", "Missing CI workflow", lambda root, ctx: not any((Path(root) / ".github/workflows").glob("*.yml"))),
    ("missing_tests", "medium", "Missing test directory", lambda root, ctx: not (Path(root) / "tests").is_dir()),
    ("prompt_drift", "high", "Agent prompt drift", lambda root, ctx: check_prompt_drift(root)),
    ("memory_contradiction", "medium", "Memory contradiction check", lambda root, ctx: False),  # placeholder
    ("oversized_files", "low", "Oversized files (>100KB)", lambda root, ctx: check_oversized(root)),
]


def check_agent_modes(root):
    agents_dir = Path(root) / "opencode-agent-pack" / "agents"
    if not agents_dir.exists():
        return False
    for f in agents_dir.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        if "mode: all" in content[:200]:
            return True  # found deprecated mode
    return False


def check_deprecated_key(root):
    agent_sh = Path(root) / "agent.sh"
    if agent_sh.exists():
        content = agent_sh.read_text(encoding="utf-8")
        if '"agents"' in content and 'pop("agents"' not in content:
            return True


def check_prompt_drift(root):
    prompts = Path(root) / "opencode-agent-pack" / "prompts"
    agents = Path(root) / "opencode-agent-pack" / "agents"
    if not prompts.exists() or not agents.exists():
        return False
    for af in agents.glob("*.md"):
        pf = prompts / f"{af.stem}.prompt.md"
        if pf.exists():
            # Simple size comparison
            asize = af.stat().st_size
            psize = pf.stat().st_size
            # Agent .md includes frontmatter, prompts do not
            if abs(asize - psize) > (asize * 0.1) and abs(asize - psize) > 200:
                return True
    return False


def check_oversized(root):
    for dirpath, _, filenames in os.walk(root):
        if "/.git/" in dirpath or "/node_modules/" in dirpath:
            continue
        for fname in filenames:
            fpath = Path(dirpath) / fname
            try:
                if fpath.stat().st_size > 100_000 and fname.endswith((".py", ".sh", ".js", ".ts", ".md")):
                    return True
            except OSError:
                pass
    return False


def cmd_run(args):
    root = Path(args.root)
    findings = []
    if args.context and Path(args.context).exists():
        with open(args.context) as f:
            ctx = json.load(f)
    else:
        ctx = {}

    for check_id, severity, desc, checker in CHECKLIST:
        try:
            if checker(root, ctx):
                findings.append({
                    "id": check_id,
                    "severity": severity,
                    "description": desc,
                    "evidence": f"Check {check_id} flagged",
                    "recommendation": get_recommendation(check_id),
                })
        except Exception:
            pass

    score = max(0, 100 - len([f for f in findings if f["severity"] == "high"]) * 15
                       - len([f for f in findings if f["severity"] == "medium"]) * 10
                       - len([f for f in findings if f["severity"] == "low"]) * 3)

    # Build report
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "# Proactive Audit Report",
        f"Generated: {timestamp}",
        "",
        "## Summary",
        f"- Score: {score}/100",
        f"- Critical: {len([f for f in findings if f['severity'] == 'high'])}",
        f"- High: {len([f for f in findings if f['severity'] == 'high'])}",
        f"- Medium: {len([f for f in findings if f['severity'] == 'medium'])}",
        f"- Low: {len([f for f in findings if f['severity'] == 'low'])}",
        "",
        "## Findings",
    ]
    for f in findings:
        lines.append(f"### {f['severity'].upper()} — {f['description']}")
        lines.append(f"Evidence: {f['evidence']}")
        lines.append(f"Recommended fix: {f['recommendation']}")
        lines.append("")

    lines.append("## Suggested Next Actions")
    if findings:
        for i, f in enumerate(findings[:5], 1):
            lines.append(f"{i}. [{f['severity']}] {f['description']}")
    else:
        lines.append("1. No issues found. Repository is in good health.")

    report = "\n".join(lines)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(report)
        print(f"Report saved: {args.out}")
    else:
        print(report)


def get_recommendation(check_id):
    recs = {
        "stale_context_index": "Run: ./agent.sh --refresh-context",
        "missing_rules": "Run: ./agent.sh --init-context",
        "missing_commands": "Run: ./agent.sh --init-context",
        "agent_mode": "Fix agent frontmatter to use primary/subagent modes",
        "deprecated_key": "Ensure config uses 'agent' not 'agents' key",
        "missing_ci": "Add .github/workflows CI workflow",
        "missing_tests": "Add test suite with tests/ directory",
        "prompt_drift": "Regenerate prompts with gen-prompts.py",
        "memory_contradiction": "Review memory.jsonl for contradictions",
        "oversized_files": "Split large files into smaller modules",
    }
    return recs.get(check_id, "Manual review recommended")


def main():
    parser = argparse.ArgumentParser(description="Proactive Audit")
    parser.add_argument("--root", required=True)
    parser.add_argument("--context")
    parser.add_argument("--out")
    args = parser.parse_args()
    cmd_run(args)


if __name__ == "__main__":
    main()
