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
scout
```

## Agents

| Agent | Mode | Purpose |
|---|---|---|
| **heidi** | all | Orchestrator — routes work to specialists, handles general tasks, manages error recovery |
| **frontend** | all | React, TypeScript, Tailwind, Next/Vite UI, UX, a11y, with decision frameworks |
| **backend** | all | APIs, databases, Prisma, auth, server logic, migrations, security protocols |
| **debugger** | all | Bugs, CI failures, regressions, root-cause analysis, with retry limits |
| **auditor** | all | Read-only code review, architecture, security analysis, with severity templates |
| **planner** | all | Feature specs, architecture plans, task breakdown, with gated approval |
| **scout** | all | Project reconnaissance, stack detection, directory mapping (read-only) |

## Architecture

```
User Request
    │
    ▼
  heidi (orchestrator)
    │
    ├── Simple task? → heidi handles it directly
    │
    ├── Unfamiliar project? → @scout → project profile
    │
    ├── UI work? → @frontend
    │
    ├── API/DB work? → @backend
    │
    ├── Bug/failure? → @debugger
    │
    ├── Code review? → @auditor
    │
    └── Large feature? → @planner → then specialists
```

## Agent Design Principles

Every agent in this pack follows these design principles:

1. **Reasoning Protocol** — Think before acting. Every agent assesses the task before executing.
2. **Anti-Patterns** — Explicit "DO NOT" lists prevent common failure modes.
3. **Retry Limits** — Hard cap of 3 attempts on any single issue, then escalate to user.
4. **Structured Output** — Consistent response formats (What I Did / Files Changed / Verification / Status).
5. **Project Discovery** — Detect the project stack from config files. Never assume React/TypeScript/Tailwind.
6. **Self-Compliance** — The orchestrator self-audits after each action.
7. **Project Rules & Memory** — All agents inspect `.heidi/rules.md` for repository constraints and auto-record learnings.

## Project Rules & Persistent Memory System (`.heidi/rules.md`)

This agent pack features a living memory system for your repository:

* **Command Registry**: Defines exact `Typecheck`, `Lint`, `Test`, and `Build` commands so agents never guess scripts.
* **Architecture Constraints**: Records framework, styling, state management, and DB/ORM rules.
* **Gotchas & Anti-Patterns**: Documents repository-specific forbidden patterns.
* **🧠 Auto-Learning Memory Protocol**: When `@heidi` or specialists fix a non-obvious bug, uncover a build/test gotcha, or receive user preferences, they automatically append a persistent rule to `## 🧠 Agent Memory & Past Learnings` in `.heidi/rules.md`.

### Initialize Project Rules

To generate a pre-populated `.heidi/rules.md` template in your workspace:

```bash
./agent.sh --init-rules
```

If `.heidi/rules.md` does not exist when `@scout` inspects a project, `@scout` will automatically draft a pre-populated template in its output report.

## Usage

Use **heidi** as your default orchestrator. Use individual agents directly when you want a specialist:

- `@heidi` — general tasks, routing to specialists
- `@scout` — project reconnaissance (run this first on new projects)
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

### Preview changes

```bash
# See what would be installed without doing it
./agent.sh --dry-run

# See diff between installed and source agents
./agent.sh --diff
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

3. **Compare source vs installed:**
   ```bash
   ./agent.sh --diff
   ```
   This shows exactly what's different between your source agents and installed agents.

4. **Run full repair:**
   ```bash
   ./agent.sh --repair
   ```
   This installs to all paths, writes JSON config, and runs diagnostics.

5. **Understand the discovery chain:**
   - `Build` and `Plan` are built-in agents — they always appear.
   - Custom agents should appear after OpenCode reloads its agent registry.
   - If agent files exist but `opencode agent list` does **not** show them → run `./agent.sh --repair`.
   - If `opencode agent list` shows them but the web UI does **not** → the current web session is stale or running from a different server/user/project. Start a new OpenCode session from the same project folder.

6. **Project install note:** `--project` and `--config-project` install relative to the current directory where `agent.sh` is run. Make sure to run it from the same project folder you open in OpenCode.

## What is not affected

Official OpenCode `build` and `plan` agents are untouched. This pack only adds new agents.

## Idempotent

Running the installer multiple times is safe. Existing agent files are backed up with a `.bak.TIMESTAMP` suffix before overwriting.
