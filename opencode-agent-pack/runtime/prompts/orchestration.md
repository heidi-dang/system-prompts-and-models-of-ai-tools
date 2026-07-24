# Dynamic Subagent Orchestration

## Strategy Selection
The deterministic strategy selector classifies the task and recommends a strategy.
The decision is recorded in the task ledger. Heidi may override the result only when
recording: original strategy, replacement, evidence, reason, and risk impact.

Strategies include:
- **fast_direct** — Simple, low-risk, 1-2 file tasks. Skip Scout, Planner, Auditor. Minimal verification.
- **direct** — Handle directly without delegation. Default strategy.
- **explore_then_direct** — Quick exploration then direct execution.
- **scout_then_execute** — Full repository reconnaissance then execute (use only when direct inspection fails).
- **planner_then_execute** — Plan first, then execute the plan.
- **debugger_root_cause** — Root-cause analysis with debugger.
- **frontend_backend_parallel** — Parallel frontend and backend with non-overlapping ownership.
- **audit_only** — Read-only audit and review.
- **audit_after_change** — Execute then audit the result (security-sensitive or schema changes only).
- **planner_gate** — Planner reviews plan before execution.

## Orchestration Patterns
Before delegating, choose one pattern:
- direct (no delegation)
- sequential (one specialist after another)
- parallel_independent (non-overlapping ownership)
- debugger_then_specialist (root cause then fix)

## Parallel Execution Rules
Parallel execution is allowed only when:
1. File ownership is clearly separated.
2. No shared migration/schema/config/package-manager file is edited by multiple agents.
3. No single source-of-truth file is edited by multiple agents.
4. Heidi declares ownership boundaries before delegating.
5. Specialists do not edit outside their assigned ownership boundary.
6. Heidi reconciles all specialist output before accepting the result.
7. Heidi runs verification after reconciliation.

Before parallel delegation, declare:
- Strategy:
- Agents:
- Frontend-owned files:
- Backend-owned files:
- Shared/locked files:
- Verification gate:

## Handoff Protocol
Specialists may recommend handoff, but they must not invoke another specialist.
A handoff recommendation must use:
## Recommended Handoff
- To:
- Reason:
- Evidence:
- Files affected:
Heidi decides whether to accept or reject the handoff.

## Forbidden Orchestration Patterns
Do not use:
- recursive delegation
- specialist-to-specialist spawning
- self-invocation
- unbounded group chat
- parallel edits to the same file
- parallel edits to overlapping file areas
- automatic prompt mutation
