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

## Legendary Heidi Runtime (v1.4.0)

Legendary Heidi preserves OpenCode's native model-specific intelligence and adds
a modular orchestration layer on top. See `docs/legendary-heidi/` for full documentation.

### Key Capabilities
- **Native Intelligence Bridge**: Composes with provider-specific prompts instead of replacing them
- **Automatic Runtime Lifecycle**: Context retrieval, strategy selection, task ledger, runtime events
- **Fast Path**: Low-overhead execution for simple tasks (typo fixes, config changes)
- **Verified Memory**: Memory Candidates replace direct rules.md mutation
- **Prompt Proposals**: Validated, evaluated, and approved prompt evolution
- **Resilience**: Failure classifier, circuit breaker, bounded retries
- **Build-vs-Heidi Benchmarks**: Deterministic grading with same-model comparisons
- **Full Lifecycle**: Install, doctor, migrate, benchmark, uninstall, rollback

### Token Governance

Heidi includes enforceable per-task token consumption limits to prevent runaway token usage (e.g., the 27M token incident).

#### How Token Accounting Works

- **Uncached input tokens**: Tokens from the request that were not served from cache.
- **Cached input tokens**: Tokens from the request that were served from cache (lower cost).
- **Output tokens**: Tokens generated by the model in the response.
- **Reasoning tokens**: Tokens used for chain-of-thought reasoning (where supported).
- **Cache-write tokens**: Tokens written to cache for future requests (full cost).

#### Default Limits

| Limit | Default | Description |
|-------|---------|-------------|
| `max_total_tokens` | 1,500,000 | Hard cap on total tokens per task |
| `max_input_tokens_per_request` | 100,000 | Max input tokens per model call |
| `max_output_tokens_per_request` | 8,000 | Max output tokens per model call |
| `max_reasoning_tokens_per_request` | 12,000 | Max reasoning tokens per model call |
| `max_model_calls` | 40 | Max model calls per task |
| `max_subagent_calls` | 8 | Max subagent calls per task |
| `max_calls_per_agent` | 3 | Max calls per individual agent |
| `max_parallel_agents` | 2 | Max concurrent agents |
| `max_audit_cycles` | 1 | Max automatic audit cycles |
| `max_equivalent_retries` | 2 | Max retries for same fingerprint |
| `warning_percent` | 70% | Warning threshold for optional delegation |
| `hard_stop_percent` | 100% | Hard stop at budget limit |
| `delegation_context_limit` | 1,500 | Target tokens for delegation handoff |
| `delegation_context_max` | 4,000 | Strict max tokens for delegation handoff |

#### Warning and Hard-Stop Behavior

- **Warning (70%)**: Optional delegation is disabled. Heidi continues with direct execution only.
- **Hard stop (100%)**: No additional model calls are made. Current work is preserved and a partial-completion report is produced.

#### Configuration Example

```json
{
  "consumption": {
    "max_total_tokens": 1500000,
    "max_input_tokens_per_request": 100000,
    "max_output_tokens_per_request": 8000,
    "max_reasoning_tokens_per_request": 12000,
    "max_model_calls": 40,
    "max_subagent_calls": 8,
    "max_calls_per_agent": 3,
    "max_parallel_agents": 2,
    "max_audit_cycles": 1,
    "max_equivalent_retries": 2,
    "warning_percent": 70,
    "hard_stop_percent": 100,
    "delegation_context_limit": 1500,
    "delegation_context_max": 4000
  }
}
```

#### Inspecting Per-Task Usage

```bash
# Check budget status during a task
python3 opencode-agent-pack/scripts/token_budget.py status --budget-file <path> --task-id <id>

# Generate a usage report
python3 opencode-agent-pack/scripts/token_budget.py report --budget-file <path> --task-id <id>
```

#### Overriding Limits

Edit the `consumption` section in `opencode-agent-pack/runtime/runtime-policy.json` and reinstall the agent pack.

#### Diagnosing Abnormal Consumption

```bash
# Run the runtime doctor
./agent.sh --runtime-doctor

# Check token governance controls
python3 opencode-agent-pack/scripts/runtime_doctor.py native-prompt
```

#### Disabling Nonessential Orchestration

Use the `fast_direct` strategy for simple tasks to skip Scout, Planner, and Auditor:

```bash
python3 opencode-agent-pack/scripts/strategy_selector.py select --task "fix typo" --context <context.json>
```
