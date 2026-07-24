# Storage

## Database

- Engine: SQLite (better-sqlite3)
- Mode: WAL for concurrent access
- Location: `~/.config/opencode/heidi-runtime/runtime.db`
- Configurable: via `dbPath` option

## Schema v1 Tables

| Table | Purpose |
|-------|---------|
| `tasks` | Task records with status and lifecycle |
| `sessions` | OpenCode session to task mapping |
| `agents` | Agent registry |
| `events` | Lifecycle event log |
| `tool_calls` | Tool invocations |
| `delegations` | Subagent delegation records |
| `routing_decisions` | Classifier results |
| `audit_runs` | Audit requests and results |
| `retry_fingerprints` | Failure fingerprints |
| `verification_runs` | Verification command results |
| `checkpoints` | State checkpoints |
| `context_items` | Context retrieval records |
| `policy_decisions` | Governance decisions |
| `budget_interfaces` | Phase 2 placeholder (no enforcement) |

## Properties

- Transactional writes
- Unique event IDs
- Parent-child relationships
- Schema versioning
- Configurable retention
- No credentials in records
