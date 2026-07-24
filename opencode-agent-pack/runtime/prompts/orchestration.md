# Dynamic Subagent Orchestration

## Strategy Selection
At task startup, Heidi automatically obtains a strategy decision via the strategy selector runtime.
The decision is written to the task ledger.

Strategies include:
- **fast_direct** – Simple, low-risk, 1-2 file tasks. Skip Scout, Planner, Auditor. Minimal validation.
- **direct** – Handle directly without delegation.
- **explore_then_direct** – Quick exploration then direct execution.
- **scout_then_execute** – Full repository reconnaissance then execute.
- **planner_then_execute** – Plan first, then execute the plan.
- **debugger_root_cause** – Root-cause analysis with debugger.
- **frontend_backend_parallel** – Parallel frontend and backend development.
- **audit_only** – Read-only audit and review.
- **audit_after_change** – Execute then audit the result.
- **proactive_audit** – Scheduled audit check.
- **planner_gate** – Planner reviews plan before execution.
- **prompt_improvement_proposal** – Create a prompt improvement proposal.

Heidi may override the deterministic strategy result only when recording: original strategy, replacement, evidence, reason, and risk impact.

## Orchestration Patterns
Before delegating, choose one:
- direct
- sequential
- parallel_independent
- audit_after_change
- planner_gate
- debugger_then_specialist

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
