# Retries and Audits

## Retry Policy

- Fingerprint: objective + strategy + agent + tool + files + error + context + env
- First failure: may retry with material change
- Second equivalent failure: change strategy or evidence
- Third equivalent failure: circuit breaker, preserve evidence
- Max equivalent retries: 2
- Environment vs code failure: classified separately

## Audit Policy

- Max automatic audit cycles: 1
- User-requested audit: 1
- Equivalent scope deduplicated via SHA-256 (scope_hash)
- Concurrent triggers → 1 audit
- Repair after audit → no automatic re-audit
- File count alone does NOT trigger audit
- Read-only audit is NOT automatically critical risk

## Deduplication Proof

Three simultaneous triggers (routing decision + security policy + user request) produce exactly one Auditor delegation.
