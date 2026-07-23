# Heidi OpenCode Agent Pack v1.2.0

A production-grade set of seven custom agents for [OpenCode](https://opencode.ai) that install alongside the built-in `Build` and `Plan` agents.

## Architecture

| Agent    | Mode       | Permission    | Purpose |
| -------- | ---------- | ------------- | ------- |
| **heidi** | `primary`  | Edit+Bash+Task | Orchestrator with task allowlist |
| **scout** | `subagent` | Read-only      | Project reconnaissance |
| **planner** | `subagent` | Read-only    | Feature planning and specs |
| **auditor** | `subagent` | Read-only    | Code review and analysis |
| **frontend** | `subagent` | Edit+Bash    | UI/React/Tailwind work |
| **backend** | `subagent` | Edit+Bash    | API/database/server work |
| **debugger** | `subagent` | Edit+Bash    | Bug fixing and root cause |

- **Heidi** uses `mode: primary` with an explicit task allowlist allowing only the six specialists.
- **Specialists** use `mode: subagent` and deny task delegation.
- **Read-only agents** (scout, planner, auditor) deny edit, bash, and task with no broad command prefixes.
- **All agents** deny restart/reboot/shutdown/logout.

## Quick Start

```bash
git clone https://github.com/heidi-dang/system-prompts-and-models-of-ai-tools.git
cd system-prompts-and-models-of-ai-tools
./agent.sh --repair
```

## Global Installation

```bash
./agent.sh                      # global (default, ~/.config/opencode/agents/)
./agent.sh --global             # explicit global
./agent.sh --config-global      # global markdown + opencode.json config
```

## Project Installation

```bash
./agent.sh --project            # per-project (.opencode/agents/)
./agent.sh --config-project     # project markdown + opencode.json config
./agent.sh --both               # both global and project
```

## JSON Configuration Generation

The installer writes to the `agent` key (singular) in `opencode.json`, never the deprecated `agents` key.

```bash
./agent.sh --config-global      # updates ~/.config/opencode/opencode.json
./agent.sh --config-project     # updates ./opencode.json
./agent.sh --default heidi --config-global   # set default agent
```

Configuration generation:
- Uses `$schema: "https://opencode.ai/config.json"`
- Preserves unrelated keys and user-defined agents
- Writes atomically via temp file + `mv`
- Validates generated config before completion
- Skips backup when content would be identical

## Rules, Commands, and Memory

```bash
./agent.sh --init-rules          # create .heidi/ with rules.md, commands.md, memory.jsonl
./agent.sh --init-rules --force  # reinitialize with backup
```

- **rules.md** — Stack-neutral repository policies (fill in detected tech)
- **commands.md** — Verified commands with evidence sources
- **memory.jsonl** — Structured durable learning records

Agents use a memory-candidate protocol: specialists propose learnings, Heidi verifies and writes only high-confidence durable entries.

### Memory Utility

```bash
python3 opencode-agent-pack/scripts/memory.py validate .heidi/memory.jsonl
python3 opencode-agent-pack/scripts/memory.py add \
  --file .heidi/memory.jsonl \
  --category bug_gotcha \
  --summary "Example" \
  --evidence "path/file:42" \
  --confidence high
python3 opencode-agent-pack/scripts/memory.py list --file .heidi/memory.jsonl
```

## Diagnostics

```bash
./agent.sh --check          # file-level inspection
./agent.sh --doctor         # runtime discovery diagnostics
./agent.sh --diff           # diff source vs installed
./agent.sh --dry-run        # preview without modifying
```

## Lifecycle

```bash
./agent.sh --uninstall       # remove managed agents and config entries
./agent.sh --rollback        # restore newest backup set
./agent.sh --version         # show pack version
```

## Task Identifiers

When using the `task` tool in prompts, pass exact agent identifiers without `@`:
- Correct: `scout`, `frontend`, `backend`, `debugger`, `auditor`, `planner`
- Incorrect: `@scout`, `@frontend`

The `@` prefix is for manual user invocation only.

## Idempotent

Running the installer multiple times is safe. Unchanged files are skipped via `cmp -s`. Backups are created only when content changes.

## Troubleshooting

If agents do not appear in the OpenCode web UI:

1. `./agent.sh --check` — verify files are installed
2. `./agent.sh --doctor` — check `opencode agent list` discovery
3. `./agent.sh --repair` — full install + config + diagnostics
4. Start a new OpenCode session from the project folder

## Testing

```bash
python3 tests/validate_agents.py          # agent definitions
python3 -m unittest tests.test_memory -v  # memory utility
bash tests/test_installer.sh              # installer suite
```
