# Resilience & Error Recovery

## Failure Classification
Failures are classified into categories: implementation, test_expectation, dependency, environment, permission, context, configuration, tool_invocation, external_service, unknown.

Each category has evidence requirements, retry allowance, permitted next strategy, and escalation conditions.

## Recovery Policy
1. **First failure**: Analyze the error, fix the root cause, rerun targeted checks.
2. **Second equivalent failure**: Change hypothesis or strategy. Do NOT retry the same approach.
3. **Third equivalent failure**: Circuit breaker opens. Record the failure. Return exact evidence and next action.

Never silently retry the same approach. Never apply the same fix twice.

## Environment Issues
If you encounter environment problems (missing dependencies, wrong runtime version, broken toolchain, Docker issues):
- Do NOT try to fix the development environment yourself.
- Report the exact error to the user.
- Suggest what they need to fix.
- If CI is available, pivot to running checks there instead.

## Circuit Breaker
Do not claim an issue is fixed unless the original failing check passes. Retry limits are configurable.

## Task Ledger
The runtime maintains a task ledger recording: start/events/finish per task. Interrupted tasks are marked as interrupted, not completed.
