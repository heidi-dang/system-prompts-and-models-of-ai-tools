#!/usr/bin/env python3
"""
Build-vs-Heidi Benchmark Infrastructure.

Commands:
  validate                              Validate benchmark schema and fixtures
  run --agent <a> --model <m> --suite <s> [--results <d>]  Run benchmarks
  compare --baseline <a> --candidate <a> --results <d>      Compare results

--model current: use the currently configured model.
--mock: use deterministic fixtures (for CI / no-real-model environments).

Metrics collected:
  task_completion, required_tests_passed, unrelated_files_changed,
  expected_files_changed, invalid_files_created, retries, tool_calls,
  elapsed_time, token_usage, audit_findings, final_repository_cleanliness,
  result_reproducibility.

Do not fabricate numbers — mark unavailable metrics as null.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ──────────────────────────────────────────────────────────────────
# Benchmark schema
# ──────────────────────────────────────────────────────────────────

BENCHMARK_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["version", "suite", "tasks"],
    "properties": {
        "version": {"type": "string"},
        "suite": {"type": "string"},
        "description": {"type": "string"},
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "prompt", "expected_files"],
                "properties": {
                    "id": {"type": "string"},
                    "prompt": {"type": "string"},
                    "expected_files": {"type": "array", "items": {"type": "string"}},
                    "required_tests": {"type": "array", "items": {"type": "string"}},
                    "forbidden_files": {"type": "array", "items": {"type": "string"}},
                    "complexity": {"enum": ["small", "medium", "large"]},
                    "timeout_s": {"type": "integer"},
                },
            },
        },
    },
}

# Mock results for deterministic CI mode
MOCK_RESULTS = {
    "task_completion": 0.92,
    "required_tests_passed": 0.88,
    "unrelated_files_changed": 1.2,
    "expected_files_changed": 0.95,
    "invalid_files_created": 0.0,
    "retries": 1.5,
    "tool_calls": None,
    "elapsed_time": None,
    "token_usage": None,
    "audit_findings": 0,
    "final_repository_cleanliness": "clean",
    "result_reproducibility": 0.98,
}


# ──────────────────────────────────────────────────────────────────
# validate command
# ──────────────────────────────────────────────────────────────────

def cmd_validate(args):
    """Validate benchmark schema and fixture files."""
    errors = []

    # Check benchmark fixture files exist
    benchmark_dir = Path("benchmarks")
    if not benchmark_dir.is_dir():
        errors.append("benchmarks/ directory not found")
    else:
        # Look for task configs in benchmarks/tasks/*/config.json
        task_configs = list(benchmark_dir.glob("tasks/*/config.json"))
        if not task_configs:
            # Fallback: look for JSON directly in benchmarks/
            task_configs = list(benchmark_dir.glob("*.json"))
        if not task_configs:
            errors.append("No benchmark task config files found in benchmarks/tasks/*/")

        for fpath in sorted(task_configs):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    errors.append(f"{fpath}: not a JSON object")
                    continue
                if "task_id" not in data and "id" not in data:
                    errors.append(f"{fpath}: missing 'task_id'")
                if "task_category" not in data and "suite" not in data:
                    errors.append(f"{fpath}: missing 'task_category'")
                if "request" not in data and "prompt" not in data:
                    errors.append(f"{fpath}: missing 'request' or 'prompt'")
            except json.JSONDecodeError as e:
                errors.append(f"{fpath}: invalid JSON: {e}")
            except Exception as e:
                errors.append(f"{fpath}: read error: {e}")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        sys.exit(1)
    print("Validation PASSED")


# ──────────────────────────────────────────────────────────────────
# run command
# ──────────────────────────────────────────────────────────────────

def cmd_run(args):
    """Run benchmarks for a given agent and model."""
    agent = args.agent
    model = args.model
    suite_name = args.suite
    results_dir = args.results or "benchmark-results"
    mock = args.mock

    # Resolve model from config when --model current
    if model == "current":
        model = _detect_current_model()
        print(f"Using current model: {model}")

    # Load fixture
    fixture_path = Path("benchmarks") / f"{suite_name}.json"
    if not fixture_path.exists():
        print(f"Error: benchmark fixture not found: {fixture_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(fixture_path, "r", encoding="utf-8") as f:
            suite = json.load(f)
    except Exception as e:
        print(f"Error: failed to read fixture: {e}", file=sys.stderr)
        sys.exit(1)

    tasks = suite.get("tasks", [])
    if not tasks:
        print("No tasks in fixture.")
        return

    results = {
        "schema_version": "1.0.0",
        "agent": agent,
        "model": model,
        "suite": suite_name,
        "mock": mock,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tasks": [],
        "aggregate": {},
    }

    for task in tasks:
        tid = task.get("id", "unknown")
        print(f"Running task: {tid}")

        if mock:
            # Deterministic mock results
            task_result = {
                "task_id": tid,
                "agent": agent,
                "model": model,
                "completed": True,
                "mock": True,
                "metrics": dict(MOCK_RESULTS),
            }
        else:
            # Placeholder for real benchmark execution
            task_result = {
                "task_id": tid,
                "agent": agent,
                "model": model,
                "completed": False,
                "mock": False,
                "metrics": {
                    "task_completion": None,
                    "required_tests_passed": None,
                    "unrelated_files_changed": None,
                    "expected_files_changed": None,
                    "invalid_files_created": None,
                    "retries": None,
                    "tool_calls": None,
                    "elapsed_time": None,
                    "token_usage": None,
                    "audit_findings": None,
                    "final_repository_cleanliness": None,
                    "result_reproducibility": None,
                },
            }
            print(f"  (mock disabled — real model execution not yet implemented)")

        results["tasks"].append(task_result)

    # Compute aggregates (only for available metrics)
    aggregates = {}
    metric_keys = [
        "task_completion", "required_tests_passed", "unrelated_files_changed",
        "expected_files_changed", "invalid_files_created", "retries",
        "tool_calls", "elapsed_time", "token_usage", "audit_findings",
        "final_repository_cleanliness", "result_reproducibility",
    ]
    for key in metric_keys:
        values = []
        for t in results["tasks"]:
            val = t.get("metrics", {}).get(key)
            if val is not None:
                values.append(val)
        if values:
            if isinstance(values[0], (int, float)):
                aggregates[f"avg_{key}"] = sum(values) / len(values)
            else:
                aggregates[key] = values[0] if all(v == values[0] for v in values) else "mixed"
        else:
            aggregates[key] = None

    results["aggregate"] = aggregates

    # Write results
    os.makedirs(results_dir, exist_ok=True)
    results_path = os.path.join(
        results_dir,
        f"{agent}-{suite_name}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json",
    )
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"\nResults written to: {results_path}")
    print(f"Tasks completed: {len([t for t in results['tasks'] if t['completed']])}/{len(tasks)}")


# ──────────────────────────────────────────────────────────────────
# compare command
# ──────────────────────────────────────────────────────────────────

def cmd_compare(args):
    """Compare baseline vs candidate results."""
    baseline_agent = args.baseline
    candidate_agent = args.candidate
    results_dir = args.results or "benchmark-results"

    if not os.path.isdir(results_dir):
        print(f"Error: results directory not found: {results_dir}", file=sys.stderr)
        sys.exit(1)

    # Find baseline and candidate result files
    baseline_files = sorted(
        [f for f in os.listdir(results_dir) if f.startswith(baseline_agent) and f.endswith(".json")],
        reverse=True,
    )
    candidate_files = sorted(
        [f for f in os.listdir(results_dir) if f.startswith(candidate_agent) and f.endswith(".json")],
        reverse=True,
    )

    if not baseline_files:
        print(f"Error: no results found for baseline '{baseline_agent}'", file=sys.stderr)
        sys.exit(1)
    if not candidate_files:
        print(f"Error: no results found for candidate '{candidate_agent}'", file=sys.stderr)
        sys.exit(1)

    baseline_path = os.path.join(results_dir, baseline_files[0])
    candidate_path = os.path.join(results_dir, candidate_files[0])

    try:
        with open(baseline_path, "r", encoding="utf-8") as f:
            baseline = json.load(f)
        with open(candidate_path, "r", encoding="utf-8") as f:
            candidate = json.load(f)
    except Exception as e:
        print(f"Error: failed to read results: {e}", file=sys.stderr)
        sys.exit(1)

    comparison = {
        "baseline": baseline_agent,
        "candidate": candidate_agent,
        "baseline_file": baseline_files[0],
        "candidate_file": candidate_files[0],
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "deltas": {},
        "verdict": "inconclusive",
    }

    b_agg = baseline.get("aggregate", {})
    c_agg = candidate.get("aggregate", {})

    metric_keys = [
        "avg_task_completion", "avg_required_tests_passed",
        "avg_unrelated_files_changed", "avg_expected_files_changed",
        "avg_invalid_files_created", "avg_retries",
        "avg_audit_findings", "result_reproducibility",
    ]

    for key in metric_keys:
        b_val = b_agg.get(key)
        c_val = c_agg.get(key)
        if b_val is not None and c_val is not None and isinstance(b_val, (int, float)) and isinstance(c_val, (int, float)):
            comparison["deltas"][key] = {
                "baseline": b_val,
                "candidate": c_val,
                "delta": round(c_val - b_val, 4),
                "delta_pct": round((c_val - b_val) / max(abs(b_val), 0.001) * 100, 1),
            }

    # Simple verdict
    completion_delta = comparison["deltas"].get("avg_task_completion", {}).get("delta", 0)
    files_delta = comparison["deltas"].get("avg_unrelated_files_changed", {}).get("delta", 0)

    if completion_delta >= 0 and files_delta <= 0:
        comparison["verdict"] = "candidate_wins"
    elif completion_delta < 0 and files_delta > 0:
        comparison["verdict"] = "baseline_wins"
    elif abs(completion_delta) < 0.02 and abs(files_delta) < 0.5:
        comparison["verdict"] = "tie"

    print(json.dumps(comparison, indent=2, sort_keys=True))


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _detect_current_model():
    """Detect the currently configured model from environment or config."""
    # Check env vars
    for env_var in ("OPENCODE_MODEL", "OPENAI_MODEL", "ANTHROPIC_MODEL"):
        val = os.environ.get(env_var)
        if val:
            return val

    # Check opencode config
    config_dir = os.environ.get(
        "OPENCODE_CONFIG_DIR",
        os.path.join(os.path.expanduser("~"), ".config", "opencode"),
    )
    config_path = os.path.join(config_dir, "opencode.json")
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return cfg.get("model") or cfg.get("default_model") or "unknown"
        except Exception:
            pass

    return "unknown"


# ──────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build-vs-Heidi Benchmark Infrastructure")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="Validate benchmark schema and fixtures")

    p_run = sub.add_parser("run", help="Run benchmarks")
    p_run.add_argument("--agent", required=True, help="Agent name (build or heidi)")
    p_run.add_argument("--model", required=True, help="Model ID or 'current'")
    p_run.add_argument("--suite", required=True, help="Benchmark suite name")
    p_run.add_argument("--results", help="Results directory")
    p_run.add_argument("--mock", action="store_true", help="Use deterministic mock results")

    p_compare = sub.add_parser("compare", help="Compare baseline vs candidate")
    p_compare.add_argument("--baseline", required=True, help="Baseline agent")
    p_compare.add_argument("--candidate", required=True, help="Candidate agent")
    p_compare.add_argument("--results", help="Results directory")

    args = parser.parse_args()

    if args.command == "validate":
        cmd_validate(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "compare":
        cmd_compare(args)


if __name__ == "__main__":
    main()
