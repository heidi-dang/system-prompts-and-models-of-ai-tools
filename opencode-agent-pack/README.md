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

### Legacy paths

Some OpenCode versions use `agent/` (singular). Install to both official and legacy paths:

```bash
./agent.sh --both --legacy
```

### JSON config fallback

If agent markdown files alone are not enough, register agents in the OpenCode JSON config:

```bash
# Project-level
./agent.sh --config-project

# Global-level
./agent.sh --config-global
```

### Max compatibility (repair)

Run all install paths, JSON config, and diagnostics:

```bash
./agent.sh --repair
```

### Set default agent

```bash
./agent.sh --default heidi --config-project
./agent.sh --default heidi --config-global
```

### Diagnostics

```bash
./agent.sh --check
./agent.sh --doctor
```

### Override config directory

```bash
OPENCODE_CONFIG_DIR=/custom/path ./agent.sh --global
```

## Troubleshooting

If the custom agents do not appear in the OpenCode web UI after installation:

1. **Check if files are installed:**
   ```bash
   ./agent.sh --check
   ```

2. **Run runtime diagnostics:**
   ```bash
   ./agent.sh --doctor
   ```
   This shows the opencode binary path, version, all agent directories, and whether `opencode agent list` finds the custom agents.

3. **Run full repair:**
   ```bash
   ./agent.sh --repair
   ```
   This installs to all paths, writes JSON config, and runs diagnostics.

4. **Understand the discovery chain:**
   - `Build` and `Plan` are built-in agents — they always appear.
   - Custom agents should appear after OpenCode reloads its agent registry.
   - If agent files exist but `opencode agent list` does **not** show them → run `./agent.sh --repair`.
   - If `opencode agent list` shows them but the web UI does **not** → the current web session is stale or running from a different server/user/project. Start a new OpenCode session from the same project folder.

5. **Project install note:** `--project` and `--config-project` install relative to the current directory where `agent.sh` is run. Make sure to run it from the same project folder you open in OpenCode.

## What is not affected

Official OpenCode `build` and `plan` agents are untouched. This pack only adds new agents.

## Idempotent

Running the installer multiple times is safe. Existing agent files are backed up with a `.bak.TIMESTAMP` suffix before overwriting.
