# Fast Path

## When Fast Path Applies
Use `fast_direct` strategy when ALL are true:
- One clear objective
- Low risk
- Likely one or two files
- No database/auth/deployment changes
- No architecture decision
- No failing CI investigation
- No user-requested audit
- No conflicting ownership
- Repository context is already sufficient

## Fast Path Behavior
1. Skip Scout.
2. Skip Planner.
3. Skip Auditor unless the change becomes high risk.
4. Avoid refreshing a fresh context index.
5. Avoid verbose progress updates for one-step work.
6. Run only the smallest reliable validation.
7. Record a lightweight ledger entry.
8. Return a concise result.

## Complexity Escalation
If a fast-path task expands beyond its predicted scope:
- Stop the fast path.
- Record the escalation.
- Choose a new strategy.
- Continue under the normal workflow.
