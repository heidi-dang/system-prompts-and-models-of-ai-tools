# Heidi OpenCode Agent Pack

A set of custom agents for OpenCode that provide specialized development assistance. These agents install alongside the official OpenCode build and plan agents without replacing them.

All custom agents use `mode: all` so they appear in the OpenCode agent selector alongside the official Build and Plan agents.

## Expected OpenCode UI

After installation, the OpenCode agent selector shows:

```
Build
Plan
heidi
frontend
backend
debugger
auditor
planner
```

## Agents

| Agent | Mode | Purpose |
|---|---|---|
| **heidi** | all | Orchestrator — routes work to specialists, handles general tasks |
| **frontend** | all | React, TypeScript, Tailwind, Next/Vite UI, UX, a11y |
| **backend** | all | APIs, databases, Prisma, auth, server logic, migrations |
| **debugger** | all | Bugs, CI failures, regressions, root-cause analysis |
| **auditor** | all | Read-only code review, architecture, security analysis |
| **planner** | all | Feature specs, architecture plans, task breakdown |

## Usage

Use **heidi** as your default orchestrator. Use individual agents directly when you want a specialist:

- `@heidi` — general tasks, routing to specialists
- `@frontend` — UI work
- `@backend` — API/database work
- `@debugger` — CI/bug/root-cause work
- `@auditor` — read-only review
- `@planner` — large feature breakdown

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

### Both

```bash
./agent.sh --both
```

### Diagnostics

```bash
./agent.sh --check
```

### Override config directory

```bash
OPENCODE_CONFIG_DIR=/custom/path ./agent.sh --global
```

## What is not affected

Official OpenCode `build` and `plan` agents are untouched. This pack only adds new agents.

## Idempotent

Running the installer multiple times is safe. Existing agent files are backed up with a `.bak.TIMESTAMP` suffix before overwriting.
