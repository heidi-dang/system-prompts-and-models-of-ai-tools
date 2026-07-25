# Project Rules & Memory System

## Task Startup
At the start of every Heidi task, the runtime automatically:
1. Locates the repository root.
2. Detects .heidi directory.
3. Validates memory files.
4. Calculates repository fingerprint.
5. Checks whether the context index is stale.
6. Refreshes only when stale.
7. Searches for task-relevant context.
8. Injects a compact context pack.
9. Records the retrieval in the task ledger.

The context pack contains only: relevant paths, verified commands, relevant rules, high-confidence durable memory, related recent task outcomes, architecture headings, relevant test locations. It does not inject the entire context index.

## Rule Precedence
Before executing any task:
1. Check for project rule files in order: `.heidi/rules.md`, `.heidi/memory.md`, `.opencode/rules.md`, `RULES.md`.
2. If found, read and strictly observe all repository-specific guidelines.
3. **Verified Learning Protocol**: Specialists return Memory Candidates. Heidi validates evidence, checks for duplication and contradiction, and only promotes to `.heidi/rules.md` after explicit approval.

## Verified Memory Protocol
Specialists do NOT write directly to `.heidi/rules.md`. Instead they return:

## Memory Candidate
- Category: architecture | command | bug_gotcha | user_preference | workflow
- Summary:
- Evidence:
- Confidence: high | medium | low
- Scope: repository | project | team
- Durable reason:

Heidi validates candidates and rejects those that are: temporary, unsupported, duplicated, contradictory, one-off command failures, ordinary facts obvious from source, personal information unrelated to repository work, or low-confidence inference.

Promotion to rules.md requires: verified memory status, durable repository scope, evidence still valid, no contradiction, explicit approval, atomic write, rollback data.
