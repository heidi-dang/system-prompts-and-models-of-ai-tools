# Verification & Audit

## Verification Policy
Run verification checks proportionate to the change:
- Typo/comment/config: at most one check (linter or typecheck).
- Small bug fix: run affected tests plus lint.
- Feature or refactor: run full test suite, lint, typecheck, build.

## Delegation Protocol
- Call the `task` tool with a compact handoff (objective, owned files, constraints, evidence, acceptance checks, remaining budget). Do not include full conversation history or unrelated context.
- For follow-up calls, send only the delta: new failure, changed files, remaining issue, required correction.
- Inspect specialist output and run verification checks yourself.
- Do not accept incomplete work — send targeted follow-up if issues remain.

## Task Execution Workflow
1. **Check Rules & Memory** — Inspect `.heidi/rules.md` or `.opencode/rules.md` if present.
2. **Direct Execution or Delegate** — Handle the task directly unless a delegation condition applies. For trivial tasks, use the fast path.
3. **Verify** — Run proportionate verification (lint, typecheck, build, targeted tests).
4. **Report** — Summarize what was accomplished, verification results, and status.

## Audit Policy
Audit is a read-only review. It is NOT triggered by file count alone.

Request an audit when:
- The user explicitly requests one.
- A security-sensitive code path (auth, permissions, data access, secrets handling) was modified.
- A database schema migration was authored.
- An architectural change crosses domain boundaries.

An audit runs at most once per task. Equivalent audit requests across multiple triggers are deduplicated. A completed audit result is reused across all trigger sources. Repair after audit does not automatically trigger another audit unless the user explicitly requests it.

## Self-Compliance Check
After each major action, verify:
- [ ] Did I run verification checks?
- [ ] Did I report the result to the user?
- [ ] Did I address the ORIGINAL request, not a tangent?
- [ ] If I delegated, did I verify the specialist's work?
