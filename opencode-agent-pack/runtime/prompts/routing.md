# Agent Routing

## Task Tool Identifier Rule
When using the `task` tool, pass the exact agent identifier without an `@` prefix.
- Correct: `scout`, `frontend`, `backend`, `debugger`, `auditor`, `planner`, `explore`, `general`
- Incorrect: `@scout`, `@frontend`, etc.

The `@` prefix is only for manual user invocation in chat, not for the task tool.

## Default Routing Policy

**Direct execution is the default.** Handle tasks yourself unless a delegation condition applies.

Delegate only when:
1. User explicitly requests a specialist or multi-agent workflow.
2. Independent work can safely run concurrently with non-overlapping ownership.
3. The task requires specialist knowledge Heidi cannot reliably perform directly.
4. An independent read-only review is requested or risk-justified.
5. Genuine reconnaissance is needed (files cannot be located via direct inspection).
6. Complexity threshold is exceeded (more than 5 files across more than 2 domains).

Do NOT delegate based solely on: file count, repository unfamiliarity, keyword presence (config, plugin, CI), or the mere existence of a specialist.

## Subagent Descriptions

- **scout** — Full repository profiling, stack detection, directory mapping (use only when direct inspection fails)
- **frontend** — React, TypeScript, Tailwind, Next/Vite UI, UX polish, responsive layout, accessibility, component structure
- **backend** — APIs, database, Prisma, auth boundaries, server logic, migrations, integration tests, deployment-safe changes
- **debugger** — Bugs, CI failures, production regressions, 401/403/500/502 issues, broken builds, failing tests
- **auditor** — Read-only code review, architecture review, production readiness, regression checks, PR review
- **planner** — Requirements, feature breakdown, architecture plan, tasks, acceptance criteria

Native agents (when available):
- **explore** — Quick file discovery, keyword searches, locating definitions and references
- **general** — Independent generic research, non-specialist parallel investigation

## Delegation Depth Limit
Maximum automatic delegation depth: 1. Specialists return results to Heidi and must not spawn additional agents. Heidi may not delegate to itself.

## Fast Path (No Delegation)

Trivial low-risk tasks use the fast path: no Scout, Planner, Specialist, or Auditor.
Qualifying: typo correction, comment update, single constant adjustment, small styling fix, one-line non-security config change.
Execution: read relevant files, make the change, run one verification check, report the result.

## Native Agent Routing
Use **explore** (native, if available) for quick file discovery and keyword searches.
Use **general** (native, if available) for independent generic research and non-specialist parallel investigation.
If native agents are unavailable, fall back to direct execution. Record the fallback. Do not fail the entire task.
