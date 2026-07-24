#!/usr/bin/env python3
"""
Generate runtime orchestration prompt from modules in opencode-agent-pack/runtime/prompts/

Modules expected (optional — missing modules are skipped with a warning):
  core.md, routing.md, orchestration.md, memory.md, verification.md,
  resilience.md, reporting.md, fast-path.md

Also regenerates prompt-only files from agent markdown (strip frontmatter).

Commands:
  (default)                     Regenerate agent prompts and runtime orchestration prompt
  --check                       Validate generated prompts have no duplicates/conflicts
  --stats                       Report prompt sizes and metrics
  --max-prompt-size <n>         Configurable max prompt size (default: 50000)
  --warn-threshold <n>          Configurable warning threshold (default: 40000)
  --hard-fail-threshold <n>     Configurable hard failure threshold (default: 60000)
  --out <path>                  Output path for runtime orchestration prompt
"""

import argparse
import os
import re
import sys
from pathlib import Path

# ──────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────

AGENTS_DIR = "opencode-agent-pack/agents"
PROMPTS_DIR = "opencode-agent-pack/prompts"
RUNTIME_PROMPTS_DIR = "opencode-agent-pack/runtime/prompts"
AGENT_NAMES = ["heidi", "frontend", "backend", "debugger", "auditor", "planner", "scout"]

RUNTIME_MODULES = [
    "core.md",
    "routing.md",
    "orchestration.md",
    "memory.md",
    "verification.md",
    "resilience.md",
    "reporting.md",
    "fast-path.md",
]

DEFAULT_OUT = "opencode-agent-pack/runtime/orchestration.prompt.md"

# Task identifier patterns to check for duplication
TASK_ID_PATTERN = re.compile(r"^(task\s+id|Task\s+ID|TASK\s+ID)", re.MULTILINE)

# ──────────────────────────────────────────────────────────────────
# Agent prompt regeneration
# ──────────────────────────────────────────────────────────────────

def regenerate_agent_prompts():
    """Regenerate prompt-only files from agent markdown."""
    os.makedirs(PROMPTS_DIR, exist_ok=True)
    generated = []
    for name in AGENT_NAMES:
        src = Path(AGENTS_DIR) / f"{name}.md"
        dst = Path(PROMPTS_DIR) / f"{name}.prompt.md"
        if not src.exists():
            print(f"WARNING: {src} not found")
            continue
        content = src.read_text(encoding="utf-8")
        # Strip YAML frontmatter
        content = re.sub(
            r'^---\n.*?\n---\n', '', content, count=1, flags=re.DOTALL
        ).lstrip("\n")
        dst.write_text(content, encoding="utf-8")
        generated.append(str(dst))
        print(f"Generated: {dst}")
    return generated


# ──────────────────────────────────────────────────────────────────
# Runtime orchestration prompt generation
# ──────────────────────────────────────────────────────────────────

def generate_runtime_prompt(out_path):
    """Generate runtime orchestration prompt from runtime/prompts modules."""
    if not os.path.isdir(RUNTIME_PROMPTS_DIR):
        print(f"WARNING: {RUNTIME_PROMPTS_DIR} not found — skipping runtime prompt generation")
        return None

    sections = []
    headings_seen = set()
    missing = []

    for module_name in RUNTIME_MODULES:
        module_path = os.path.join(RUNTIME_PROMPTS_DIR, module_name)
        if not os.path.isfile(module_path):
            missing.append(module_name)
            print(f"INFO: Runtime module {module_name} not found — skipping")
            continue

        content = Path(module_path).read_text(encoding="utf-8")

        # Extract headings for dedup
        for match in re.finditer(r"^#{1,6}\s+(.+)$", content, re.MULTILINE):
            heading = match.group(1).lower().strip()
            if heading in headings_seen:
                print(f"WARNING: duplicate heading '{heading}' in {module_name}")
            headings_seen.add(heading)

        sections.append(content)

    if not sections:
        print("ERROR: No runtime modules found. Cannot generate orchestration prompt.")
        return None

    # Compose prompt with deterministic order (same as RUNTIME_MODULES)
    composed = "\n\n".join(sections)

    # Deduplicate task identifier sections
    task_id_sections = list(TASK_ID_PATTERN.finditer(composed))
    if len(task_id_sections) > 1:
        # Remove all but the first occurrence
        for match in task_id_sections[1:]:
            # Find the line containing this match
            start = match.start()
            # Find end of paragraph
            end = composed.find("\n\n", start)
            if end == -1:
                end = len(composed)
            composed = composed[:start] + composed[end:]
        print("INFO: Removed duplicate Task identifier sections")

    # Check for conflicting memory instructions
    memory_conflicts = check_memory_conflicts(composed)
    if memory_conflicts:
        print(f"WARNING: potential memory instruction conflicts: {memory_conflicts}")

    # Check for fake reliability percentages
    fake_pcts = re.findall(r"(\d{2,3})%\s*(?:reliab|success|accurate|correct)", composed, re.IGNORECASE)
    if fake_pcts:
        print(f"WARNING: Reliability percentages found in prompt: {fake_pcts}%")

    # Write
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    Path(out_path).write_text(composed, encoding="utf-8")
    print(f"Generated runtime orchestration: {out_path}")

    if missing:
        print(f"Missing runtime modules: {', '.join(missing)}")

    return composed


def check_memory_conflicts(text):
    """Check for conflicting memory-related instructions."""
    conflicts = []
    memory_sections = re.findall(
        r"(?:memory|remember|recall).*?(?:always|never).*?(?:\n|$)",
        text, re.IGNORECASE
    )
    if len(memory_sections) > 3:
        conflicts.append("multiple memory instructions detected")
    return conflicts


# ──────────────────────────────────────────────────────────────────
# --check: validate generated prompts
# ──────────────────────────────────────────────────────────────────

def cmd_check(args):
    """Validate generated prompts for duplicates and conflicts."""
    errors = []

    # Check runtime prompt if it exists
    runtime_out = args.out or DEFAULT_OUT
    if os.path.isfile(runtime_out):
        content = Path(runtime_out).read_text(encoding="utf-8")

        # Duplicate headings
        headings = re.findall(r"^#{1,6}\s+(.+)$", content, re.MULTILINE)
        heading_counts = {}
        for h in headings:
            h_lower = h.lower().strip()
            heading_counts[h_lower] = heading_counts.get(h_lower, 0) + 1
        dups = {k: v for k, v in heading_counts.items() if v > 1}
        if dups:
            for h, count in dups.items():
                errors.append(f"duplicate heading (x{count}): '{h}'")
        else:
            print("No duplicate headings found.")

        # Task identifier duplication
        task_ids = TASK_ID_PATTERN.findall(content)
        if len(task_ids) > 1:
            errors.append(f"duplicate Task identifier sections: {len(task_ids)} found")
        else:
            print("Task identifier: OK")

        # Conflicting memory instructions
        memory_conflicts = check_memory_conflicts(content)
        for mc in memory_conflicts:
            errors.append(mc)
        if not memory_conflicts:
            print("Memory instructions: OK")

        # Fake reliability percentages
        fake_pcts = re.findall(r"(\d{2,3})%\s*(?:reliab|success|accurate|correct)", content, re.IGNORECASE)
        if fake_pcts:
            errors.append(f"fake reliability percentages: {', '.join(fake_pcts)}%")
        else:
            print("Reliability claims: OK")

        # Framework-specific assumptions
        framework_assumptions = re.findall(
            r"(?:this\s+(?:framework|library|tool)\s+(?:always|requires|expects))",
            content, re.IGNORECASE
        )
        if framework_assumptions:
            errors.append(f"framework-specific assumptions found: {len(framework_assumptions)}")
        else:
            print("Framework assumptions: OK")

    else:
        print(f"INFO: Runtime prompt not found at {runtime_out} — skipping check")

    # Check agent prompts
    for name in AGENT_NAMES:
        prompt_path = Path(PROMPTS_DIR) / f"{name}.prompt.md"
        if not prompt_path.exists():
            continue
        content = prompt_path.read_text(encoding="utf-8")
        # Check for duplicate headings within a single prompt
        headings = re.findall(r"^#{1,6}\s+(.+)$", content, re.MULTILINE)
        h_counts = {}
        for h in headings:
            h_counts[h.lower().strip()] = h_counts.get(h.lower().strip(), 0) + 1
        dups = {k: v for k, v in h_counts.items() if v > 1}
        if dups:
            for h, count in dups.items():
                errors.append(f"{name}.prompt.md: duplicate heading (x{count}): '{h}'")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        sys.exit(1)
    else:
        print("Validation PASSED")


# ──────────────────────────────────────────────────────────────────
# --stats: report prompt sizes and metrics
# ──────────────────────────────────────────────────────────────────

def cmd_stats(args):
    """Report prompt sizes and metrics."""
    print("=== Prompt Size Report ===")
    print()

    total_bytes = 0
    prompt_sizes = {}

    # Agent prompts
    print("Agent prompts:")
    for name in sorted(AGENT_NAMES):
        prompt_path = Path(PROMPTS_DIR) / f"{name}.prompt.md"
        if prompt_path.exists():
            size = prompt_path.stat().st_size
            lines = len(prompt_path.read_text(encoding="utf-8").splitlines())
            prompt_sizes[name] = size
            total_bytes += size
            print(f"  {name}.prompt.md: {size:>6} bytes, {lines:>4} lines")
        else:
            print(f"  {name}.prompt.md: MISSING")

    # Runtime prompt
    runtime_out = args.out or DEFAULT_OUT
    if os.path.isfile(runtime_out):
        size = os.path.getsize(runtime_out)
        lines = len(Path(runtime_out).read_text(encoding="utf-8").splitlines())
        prompt_sizes["runtime/orchestration"] = size
        total_bytes += size
        print(f"  runtime/orchestration.prompt.md: {size:>6} bytes, {lines:>4} lines")
    else:
        print(f"  runtime/orchestration.prompt.md: MISSING")

    # Summary
    max_size = args.max_prompt_size or 50000
    warn = args.warn_threshold or 40000
    hard_fail = args.hard_fail_threshold or 60000

    print()
    print(f"Total prompt bytes: {total_bytes}")
    print(f"Max configured size: {max_size}")
    print(f"Warning threshold: {warn}")
    print(f"Hard fail threshold: {hard_fail}")

    # Check thresholds
    for name, size in prompt_sizes.items():
        if size > hard_fail:
            print(f"CRITICAL: {name} ({size} bytes) exceeds hard fail threshold ({hard_fail})")
        elif size > warn:
            print(f"WARNING: {name} ({size} bytes) exceeds warning threshold ({warn})")

    if total_bytes > max_size:
        overage = total_bytes - max_size
        pct = (overage / max_size) * 100
        print(f"WARNING: Total prompt size ({total_bytes} bytes) exceeds max ({max_size}) by {overage} bytes ({pct:.1f}%)")

    print()
    print("=== Module breakdown ===")
    if os.path.isdir(RUNTIME_PROMPTS_DIR):
        for module_name in RUNTIME_MODULES:
            module_path = os.path.join(RUNTIME_PROMPTS_DIR, module_name)
            if os.path.isfile(module_path):
                size = os.path.getsize(module_path)
                lines = len(Path(module_path).read_text(encoding="utf-8").splitlines())
                print(f"  {module_name}: {size:>6} bytes, {lines:>4} lines")
            else:
                print(f"  {module_name}: MISSING")
    else:
        print(f"  (runtime prompts directory not found: {RUNTIME_PROMPTS_DIR})")

    # Metrics JSON
    metrics = {
        "total_bytes": total_bytes,
        "max_prompt_size": max_size,
        "warn_threshold": warn,
        "hard_fail_threshold": hard_fail,
        "modules": {
            name: {
                "bytes": size,
                "exceeds_warn": size > warn,
                "exceeds_hard_fail": size > hard_fail,
            }
            for name, size in prompt_sizes.items()
        },
    }
    print()
    print("=== Metrics JSON ===")
    import json
    print(json.dumps(metrics, indent=2, sort_keys=True))


# ──────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate runtime orchestration prompt and agent prompts"
    )
    parser.add_argument("--check", action="store_true", help="Validate generated prompts")
    parser.add_argument("--stats", action="store_true", help="Report prompt sizes and metrics")
    parser.add_argument("--max-prompt-size", type=int, default=50000, help="Max prompt size")
    parser.add_argument("--warn-threshold", type=int, default=40000, help="Warning threshold")
    parser.add_argument("--hard-fail-threshold", type=int, default=60000, help="Hard fail threshold")
    parser.add_argument("--out", help="Output path for runtime orchestration prompt")

    args = parser.parse_args()

    # Store thresholds on args for stats command
    args.max_prompt_size = args.max_prompt_size
    args.warn_threshold = args.warn_threshold
    args.hard_fail_threshold = args.hard_fail_threshold

    if args.check:
        cmd_check(args)
    elif args.stats:
        cmd_stats(args)
    else:
        # Default: generate everything
        print("=== Regenerating agent prompts ===")
        regenerate_agent_prompts()
        print()

        print("=== Generating runtime orchestration prompt ===")
        out_path = args.out or DEFAULT_OUT
        generate_runtime_prompt(out_path)
        print()

        print("=== Generation complete ===")


if __name__ == "__main__":
    main()
