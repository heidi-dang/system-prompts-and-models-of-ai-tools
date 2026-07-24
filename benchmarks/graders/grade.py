#!/usr/bin/env python3
"""
Benchmark grader — deterministic scoring for Heidi vs Build comparison.
Used by benchmark.py. Can also be invoked standalone.

Commands:
  grade --task <config.json> --result <result.json> --fixture-root <dir>
"""

import argparse
import json
import os
import sys
from pathlib import Path


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def calculate_score(expected, actual, forbidden, task_config):
    """Calculate a 0-100 benchmark score based on config and result."""
    score = 100
    deductions = []
    evidence = []

    # 1. Task completion
    if task_config.get("expected", {}).get("completion_required", True):
        if not actual.get("task_completed", False):
            deductions.append(("completion", 50, "Task not completed"))
            score -= 50
        else:
            evidence.append("Task completed: PASS")

    # 2. Required tests passed
    required_tests = task_config.get("expected", {}).get("tests_must_pass", [])
    passed_tests = set(actual.get("tests_passed", []))
    for test in required_tests:
        if test not in passed_tests:
            deductions.append(("test_missing", 15, f"Required test not passed: {test}"))
            score -= 15
    if required_tests:
        evidence.append(f"Required tests: {len([t for t in required_tests if t in passed_tests])}/{len(required_tests)} passed")

    # 3. Unrelated files changed
    expected_files = set(task_config.get("expected", {}).get("files_changed", []))
    actual_files = set(actual.get("files_changed", []))
    unrelated = actual_files - expected_files
    if unrelated and expected_files:
        deduction = min(30, len(unrelated) * 10)
        deductions.append(("unrelated_files", deduction, f"Unrelated files changed: {sorted(unrelated)}"))
        score -= deduction
    if expected_files:
        evidence.append(f"Expected files: {len(actual_files & expected_files)}/{len(expected_files)} matched")

    # 4. Max files constraint
    max_files = task_config.get("expected", {}).get("max_files_changed")
    if max_files is not None and len(actual_files) > max_files:
        excess = len(actual_files) - max_files
        deduction = excess * 5
        deductions.append(("max_files", deduction, f"Changed {len(actual_files)} files, max {max_files}"))
        score -= deduction

    # 5. Forbidden checks
    forbidden_untouched = task_config.get("forbidden", {}).get("files_untouched", [])
    for forbidden_file in forbidden_untouched:
        if any(af.startswith(forbidden_file.rstrip("/")) or forbidden_file in af for af in actual_files):
            deductions.append(("forbidden_edit", 20, f"Modified forbidden path: {forbidden_file}"))
            score -= 20

    if task_config.get("forbidden", {}).get("no_new_files") and actual.get("files_created", 0) > 0:
        deductions.append(("new_files", 15, f"Created {actual['files_created']} new files"))
        score -= 15

    if task_config.get("forbidden", {}).get("no_config_changes", False):
        config_patterns = [".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", "package.json"]
        for f in actual_files:
            if any(f.endswith(p) or f.endswith(p.replace(".", "/")) for p in config_patterns):
                deductions.append(("config_change", 15, f"Modified config file: {f}"))
                score -= 15
                break

    # 6. Retries
    retries = actual.get("retries", 0)
    if retries > 1:
        deduction = min(15, (retries - 1) * 5)
        deductions.append(("retries", deduction, f"Used {retries} retries"))
        score -= deduction

    # 7. Unavailable metrics — no deduction, just note
    unavailable = []
    for key in ["tool_calls", "token_usage", "elapsed_time"]:
        if actual.get(key) is None:
            unavailable.append(key)

    return {
        "score": max(0, score),
        "deductions": deductions,
        "evidence": evidence,
        "metrics": {
            "task_completed": actual.get("task_completed", False),
            "files_changed": len(actual_files),
            "expected_files_matched": len(actual_files & expected_files) if expected_files else None,
            "retries": retries,
            "elapsed_time": actual.get("elapsed_time"),
            "tool_calls": actual.get("tool_calls"),
            "token_usage": actual.get("token_usage"),
            "unavailable_metrics": unavailable,
            "audit_findings": actual.get("audit_findings", 0),
            "repository_cleanliness": actual.get("repository_cleanliness", "unknown"),
            "result_reproducible": actual.get("result_reproducible"),
        }
    }


def cmd_grade(args):
    task_config = load_json(args.task)
    actual = load_json(args.result)

    result = calculate_score(task_config.get("expected", {}), actual, task_config.get("forbidden", {}), task_config)

    print(json.dumps(result, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description="Benchmark Grader")
    sub = parser.add_subparsers(dest="command", required=True)

    p_grade = sub.add_parser("grade", help="Grade a benchmark result")
    p_grade.add_argument("--task", required=True, help="Task config JSON")
    p_grade.add_argument("--result", required=True, help="Result JSON")
    p_grade.add_argument("--fixture-root", help="Fixture root directory")

    args = parser.parse_args()
    if args.command == "grade":
        cmd_grade(args)


if __name__ == "__main__":
    main()
