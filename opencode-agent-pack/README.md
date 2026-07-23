# Heidi OpenCode Agent Pack

A set of custom agents for OpenCode that provide specialized development assistance. These agents install alongside the official OpenCode build and plan agents without replacing them.

## Agents

| Agent | Mode | Purpose |
|---|---|---|
| **heidi** | primary | Orchestrator — routes work to subagents, handles general tasks |
| **frontend** | subagent | React, TypeScript, Tailwind, Next/Vite UI, UX, a11y |
| **backend** | subagent | APIs, databases, Prisma, auth, server logic, migrations |
| **debugger** | subagent | Bugs, CI failures, regressions, root-cause analysis |
| **auditor** | subagent | Read-only code review, architecture, security analysis |
| **planner** | subagent | Feature specs, architecture plans, task breakdown |

## Usage

Use **heidi** as your main agent. It will route work to the right specialist:

- `@frontend` for UI work
- `@backend` for API/database work
- `@debugger` for CI/bug/root-cause work
- `@auditor` for read-only review
- `@planner` for large feature breakdown

## Installation

### Global install (default)

Installs into `~/.config/opencode/agents/` (or `$OPENCODE_CONFIG_DIR/agents`).

```bash
./agent.sh
```

### Per-project install

Installs into `.opencode/agents/` in the current directory.

```bash
./agent.sh --project
```

### Override config directory

```bash
OPENCODE_CONFIG_DIR=/custom/path ./agent.sh --global
```

## What is not affected

Official OpenCode `build` and `plan` agents are untouched. This pack only adds new agents.

## Idempotent

Running the installer multiple times is safe. Existing agent files are backed up with a `.bak.TIMESTAMP` suffix before overwriting.
