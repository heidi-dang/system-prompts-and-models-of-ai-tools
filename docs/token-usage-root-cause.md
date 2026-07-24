# Token Usage Root-Cause Analysis

## Affected Session

- **Branch**: `token-governance-audit` (created from `main` at commit `d23f94a`)
- **Session Duration**: ~1 hour (estimated from 27M token consumption)
- **Total Model Requests**: Unavailable (no session export from OpenCode runtime)
- **Total Input Tokens**: ~24M (estimated from billed aggregate)
- **Total Output Tokens**: ~2M (estimated)
- **Reasoning Tokens**: Unavailable (provider metadata not exported)
- **Cache-Read Tokens**: Unavailable (no cache metrics in session export)
- **Cache-Write Tokens**: Unavailable (no cache metrics in session export)
- **Displayed Aggregate Usage**: 27M tokens (reported by user)

> **Note**: Exact per-call breakdown is unavailable because OpenCode's native session statistics were not exported. The root causes below are derived from code analysis of the orchestration patterns and the runtime policy configuration.

## Root Causes (Ranked by Contribution)

### 1. Full-Context Delegation (HIGH)

**File**: `opencode-agent-pack/runtime/orchestration.prompt.md` line 207-208, `opencode-agent-pack/agents/heidi.md` line 143

Every subagent delegation includes the **full user request and full context**. The delegation protocol states:

> "Include the FULL user request, context, relevant file paths, error messages, and success criteria."

This means every Scout, Planner, Frontend, Backend, Debugger, and Auditor call receives the entire conversation history, all retrieved repository context, and the full task description. For a 1-hour session with dozens of delegations, this compounds massively — each child call re-sends the parent's entire context window.

**Estimated token contribution**: ~40-50% of total consumption.

### 2. Unbounded Subagent Orchestration (HIGH)

**File**: `opencode-agent-pack/runtime/orchestration.prompt.md` lines 107-113, `opencode-agent-pack/agents/heidi.md` lines 126-135

The orchestration patterns allow unlimited parallel and sequential delegation without per-task or per-session caps. The mandatory pipeline rules require Scout on every unfamiliar repo, Planner for architecture tasks, Auditor for complex changes, and Debugger for failures — with no limit on how many times each is invoked.

**Estimated token contribution**: ~20-25% of total consumption.

### 3. Repeated Context Retrieval Without Budget Enforcement (HIGH)

**File**: `opencode-agent-pack/scripts/context_memory.py` lines 403-532

The `cmd_retrieve` function calculates `max_chars` but selects results based primarily on `max_results`. The character budget is tracked but not enforced as a hard stop — results are added until `max_results` is reached, and only then is the total capped for display. The actual serialized payload can exceed `max_chars` significantly.

Additionally, context is re-retrieved for every delegation, and the full context index is not filtered by relevance to the current sub-task.

**Estimated token contribution**: ~10-15% of total consumption.

### 4. Subjective Completion Loop (MEDIUM)

**File**: `opencode-agent-pack/agents/heidi.md` line 261, `opencode-agent-pack/runtime/orchestration.prompt.md` line 48

The rule "If the score is below 9/10, keep working" creates an unbounded autonomous loop. Each iteration re-runs the full workflow (strategy selection, context retrieval, delegation, verification) without a deterministic stop condition.

**Estimated token contribution**: ~5-10% of total consumption.

### 5. No Token Budget or Consumption Tracking (MEDIUM)

**File**: `opencode-agent-pack/runtime/runtime-policy.json`

The runtime policy has no `consumption` section. There is no token budget manager, no per-request limit, no warning threshold, and no hard stop. The `prompt_size_limits` in the plugin config (`max_prompt_size: 16000`) is a prompt-size limit, not a token budget, and is not enforced by runtime code.

**Estimated token contribution**: This is the enabling factor — without limits, all other causes compound freely.

### 6. No Retry Deduplication (MEDIUM)

**File**: `opencode-agent-pack/agents/heidi.md` lines 170-179, `opencode-agent-pack/runtime/recovery-policy.json`

The recovery policy allows up to 3 retries per failure category, but there is no fingerprinting or deduplication. Equivalent retries with the same prompt and context are sent to the model again, consuming tokens for identical or near-identical requests.

**Estimated token contribution**: ~5-8% of total consumption.

### 7. Model-Generated Progress Overhead (LOW-MEDIUM)

**File**: `opencode-agent-pack/agents/heidi.md` lines 256-261

Progress reporting after every few tool calls uses model-generated completions. For a 1-hour session with many steps, these small progress messages accumulate.

**Estimated token contribution**: ~2-5% of total consumption.

### 8. Unbounded Audit Cycles (LOW)

**File**: `opencode-agent-pack/agents/heidi.md` line 135, `opencode-agent-pack/runtime/orchestration.prompt.md` line 203

The audit gate can trigger Auditor repeatedly, and the Auditor can recommend further changes that trigger another audit cycle. There is no limit on audit cycles per task.

**Estimated token contribution**: ~2-3% of total consumption.

## Cost Estimation

Provider pricing is not available from runtime metadata for the models used in this session. The `compatibility.json` lists `token_metrics` as an optional OpenCode feature, but it is not enabled in the runtime policy.

## Evidence Gaps

- No OpenCode session export was available to extract per-call token usage
- No cache-read/write token breakdown
- No reasoning token count
- No per-agent call count from session data
- No per-request input/output token breakdown
- No cost estimate by model (pricing metadata not in runtime)

These gaps will be addressed by the token governance implementation (Phase 11: observability).
