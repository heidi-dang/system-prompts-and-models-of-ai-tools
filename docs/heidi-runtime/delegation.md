# Delegation

## Contract Structure

Every delegation specifies:
- Parent task ID
- Child ID
- Agent role
- Objective
- Success criteria
- Owned files / paths
- Readable / prohibited paths
- Allowed tools
- Context pack
- Verification requirement
- Timeout (default: 5 min)
- Max retries (default: 2)

## Rules

1. Maximum 1 delegation level
2. Children cannot delegate
3. Maximum 2 implementation specialists
4. Parallel work requires non-overlapping ownership
5. Child output structured with: work completed, files changed, verification, unresolved issues, confidence
6. Parent performs reconciliation
7. No full transcript handoff
8. Simple tasks must not delegate
9. File ownership violations blocked when hook allows
10. When hard enforcement impossible, fail capability check

## Ownership Collision

Two parallel agents cannot own and edit the same file.
Verified by collision tests.
