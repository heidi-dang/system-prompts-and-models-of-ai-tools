# Verification Engine

## Categories

| Category | Description |
|----------|-------------|
| `lint` | Linter check |
| `typecheck` | TypeScript/Python type check |
| `test` | Unit/integration test run |
| `build` | Project build |
| `diff` | Manual diff inspection |
| `security` | Security scan |
| `schema` | Schema migration check |

## Selection

Verification selected based on:
- Changed paths
- Operation type
- Repository commands
- Task risk
- User requirements

## Completion Gate

A task completes when:
1. Required changes exist
2. Required verification ran
3. Mandatory verification passed
4. Unrelated drift reported
5. Remaining failures explicit
6. Confidence meets threshold (0.95 for full tasks, lower for fast path)
7. No hidden verification failure
8. No unconditional PASS

A small documentation edit does not require a full production test suite.
