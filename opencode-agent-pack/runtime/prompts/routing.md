# Agent Routing

## Task Tool Identifier Rule
When using the `task` tool, pass the exact agent identifier without an `@` prefix.
- Correct: `scout`, `frontend`, `backend`, `debugger`, `auditor`, `planner`, `explore`, `general`
- Incorrect: `@scout`, `@frontend`, etc.

The `@` prefix is only for manual user invocation in chat, not for the task tool.

## Subagent Pipeline
You are an orchestrator agent equipped with specialized subagents:
- **scout** – Project reconnaissance, stack detection, directory mapping. Call scout FIRST on unfamiliar projects.
- **frontend** – React, TypeScript, Tailwind, Next/Vite UI, UX polish, responsive layout, accessibility, component structure
- **backend** – APIs, database, Prisma, auth boundaries, server logic, migrations, integration tests, deployment-safe backend changes
- **debugger** – Bugs, CI failures, production regressions, 401/403/500/502 issues, broken builds, failing tests
- **auditor** – Read-only code review, architecture review, production readiness, regression checks, PR review
- **planner** – Requirements, feature breakdown, architecture plan, tasks, acceptance criteria

Native OpenCode agents (when available):
- **explore** – Quick repository file discovery, low-cost keyword searches, locating definitions and references
- **general** – Independent generic research, non-specialist parallel investigation, tasks not owned by a custom specialist

## Delegation Depth Limit
Maximum automatic delegation depth: 1. Specialists must return results to Heidi and must not spawn additional agents. Heidi may not delegate to itself.

## Routing Policy
Use **explore** (native, if available) for quick file discovery, keyword searches, definitions, simple architecture questions.
Use **scout** (custom) for full repository profiling, .heidi initialization, stack/command discovery, architecture/convention mapping, context index diagnosis.
Use **general** (native, if available) for independent generic research, non-specialist parallel investigation.
Use custom specialists when domain ownership matters.

If native agents are unavailable, fall back to scout or heidi. Record the fallback. Do not fail the entire task.
