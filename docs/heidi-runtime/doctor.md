# Runtime Doctor

## Checks (Phase 1)

| # | Check | Type | Failure |
|---|-------|------|---------|
| 1 | Plugin loadable | PASS/FAIL | Exit code 1 |
| 2 | Database writable | PASS/FAIL | Exit code 1 |
| 3 | Database migrations current | PASS/FAIL | Exit code 1 |
| 4 | Prompt consistency valid | PASS/FAIL | Exit code 1 |
| 5 | Direct execution is default | PASS/FAIL | Exit code 1 |
| 6 | Fast path does not delegate | PASS/FAIL | Exit code 1 |
| 7 | Governance denies dangerous commands | PASS/FAIL | Exit code 1 |
| 8 | Governance allows repository operations | PASS/FAIL | Exit code 1 |
| 9 | Audit deduplication active | PASS/FAIL | Exit code 1 |
| 10 | Retry circuit breaker active | PASS/FAIL | Exit code 1 |
| 11 | Phase 2 not falsely claimed | PASS/FAIL | Exit code 1 |
| 12 | Agent registry clean | SKIP (isolated) / PASS | Exit code 1 |
| 13 | Installed prompt composition independent | SKIP (isolated) / PASS | Exit code 1 |

## Output

```
PASS: Plugin loadable
PASS: Database writable
PASS: Database migrations current
FAIL: Prompt consistency valid (prompt consistency check failed)
PASS: Direct execution is default
...

Summary: 10 PASS, 1 FAIL, 2 SKIP
```

Machine-readable JSON available in output.
