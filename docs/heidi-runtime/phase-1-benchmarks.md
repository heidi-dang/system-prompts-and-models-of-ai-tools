# Phase 1 Benchmarks

## Scenarios

| # | Scenario | Expected Strategy | Max Agents | Max Audits |
|---|----------|------------------|------------|------------|
| 1 | README typo | fast_path | 0 | 0 |
| 2 | Small frontend defect | direct or single_specialist | 1 | 0 |
| 3 | Small backend validation defect | direct or single_specialist | 1 | 0 |
| 4 | Full-stack feature | parallel_specialists | 2 | 1 |
| 5 | Production authentication issue | debug_investigation | 1 | 1 |
| 6 | Audit-only request | audit_only | 1 | 1 |
| 7 | Repeated equivalent failure | — | — | — |
| 8 | Conflicting parallel ownership | — | — | — |
| 9 | Dangerous machine-level command | — | — | — |
| 10 | Local dependency install | — | — | — |
| 11 | Runtime reload recovery | — | — | — |
| 12 | Missing context source | — | — | — |

## Performance Thresholds

| Metric | Threshold |
|--------|-----------|
| Trivial task model calls | ≤ 2 |
| Small task subagents | ≤ 1 |
| Full-stack max model calls | ≤ 8 |
| Full-stack max specialists | ≤ 2 |
| Audit max | 1 |
| Equivalent retries max | 2 |
| Repeated file reads reduction | ≥ 50% |
| Delegation context size reduction | ≥ 50% |
| Mandatory scout count | 0 |
| Nested delegation count | 0 |

## Reporting

For each benchmark, report:
- Selected strategy
- Model call count (or "unobservable")
- Tool call count
- Subagent count
- Audit count
- Retry count
- Context pack size
- Repeated reads
- Verification commands
- Elapsed time
- Final state
- Expected vs actual result
