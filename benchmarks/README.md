# Legendary Heidi — Build vs Heidi Benchmarks

## Methodology

Benchmarks compare Build and Heidi agents using the **same model**, **same fixture repository**, **same initial commit**, and **same user request**. Results are graded deterministically.

## Running Benchmarks

### Mock/Dry-Run (CI)
```bash
python3 opencode-agent-pack/scripts/benchmark.py validate
./agent.sh --benchmark-smoke
```

### Real-Model (Opt-in, requires OpenCode)
```bash
python3 opencode-agent-pack/scripts/benchmark.py run \
  --agent build \
  --agent heidi \
  --model current \
  --suite smoke

python3 opencode-agent-pack/scripts/benchmark.py compare \
  --baseline build \
  --candidate heidi \
  --results benchmarks/results
```

## Metrics

| Metric | Description | Availability |
|--------|-------------|-------------|
| task_completion | Whether the task was completed | Always |
| required_tests_passed | Tests that must pass | When defined |
| unrelated_files_changed | Files not in expected set | When defined |
| expected_files_changed | Expected files that were changed | When defined |
| invalid_files_created | Files created that should not exist | When defined |
| retries | Number of retries used | Always |
| tool_calls | Number of tool invocations | Available |
| elapsed_time | Wall clock duration | Always |
| token_usage | Token consumption | When exposed |
| audit_findings | Audit issues found | For audit tasks |
| repository_cleanliness | Clean working tree after task | Always |
| result_reproducibility | Whether same result is reproducible | Optional |

## Acceptance Thresholds

| Threshold | Target |
|-----------|--------|
| Fast-path median completion time (Heidi vs Build) | No more than 20% slower |
| Fast-path correctness | Not lower than Build |
| Complex-task correctness | Higher than or equal to Build |
| Unrelated-diff rate | Lower than or equal to Build |
| Production-audit finding precision | Higher than or equal to Build |
| Critical regression | None in any category |

## Task Categories

| Category | Description | Complexity | Risk |
|----------|-------------|-----------|------|
| fast-one-line-edit | Single typo/config fix | small | low |
| isolated-bug | Focused bug fix | medium | medium |
| unfamiliar-code-search | Locate code in new repo | medium | low |
| failing-ci | Diagnose broken CI | medium | high |
| fullstack-feature | FE + BE feature | large | medium |
| database-change | Migration/schema change | medium | high |
| production-audit | Readiness audit | large | low |

## Important Notes

- **Do not fabricate benchmark numbers.** All results must be from actual runs.
- Mark unavailable metrics as `null`.
- Real-model benchmarks are opt-in (scheduled/manual workflow only).
- CI uses mocked deterministic fixtures.
