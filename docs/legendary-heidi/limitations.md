# Legendary Heidi — Limitations and Known Gaps

## Runtime Limitations
- **OpenCode Plugin API**: Not available in tested versions. Composite prompt generation is the fallback.
  When the plugin API is introduced, the `plugins/` directory provides the migration path.
- **Session Hooks**: No pre/post-task hooks available in OpenCode. Task ledger start/finish
  must be triggered by Heidi's initial instructions rather than automatic hooks.
- **Token/Tool Metrics**: OpenCode does not expose token usage or tool call counts to agent prompts.
  Benchmark metrics for these are marked "unavailable" in reports.
- **Model-Level Prompt Composition**: OpenCode replaces the native prompt when a custom agent
  definition is loaded. Heidi's composite prompt approach mitigates this, but true composition
  (append/prepend) would require OpenCode API support.

## Verification Limitations
- **Runtime Doctor**: Can only check prompt presence, not model behavior. Passes when OpenCode
  is unavailable but reports "UNAVAILABLE" status.
- **Benchmark Smoke**: CI uses deterministic mocked fixtures. Real-model benchmarks require
  opt-in workflow with OpenCode installed and a configured model.
- **Native Agent Detection**: explore and general agents are detected via `opencode agent list`
  when OpenCode is available, otherwise reported as "unavailable".

## Compatibility Limitations
- **OpenCode Version**: Tested against a specific version. Newer versions may introduce
  breaking changes to agent definition schema or prompt resolution.
- **Model Families**: No hardcoded model IDs, but new provider families may require
  updated prompt composition validation.
- **Config Schema**: Agent frontmatter schema changes are caught by validate_agents.py,
  but semantic changes may require manual review.

## Operational Limitations
- **Task Ledger Auto-Start**: Without session hooks, Heidi must be instructed to start the
  ledger. The runtime instructions make this part of Heidi's task startup behavior, but
  it depends on Heidi following instructions.
- **Proactive Audit**: Does not run automatically without triggers. Requires either
  configured interval, file change detection, or manual invocation.
- **Memory Promotion**: Requires explicit approval. Cannot auto-promote, even high-confidence
  candidates (by design — this is a safety feature, not a bug).

## Not Yet Implemented
- Real-time runtime events streaming (file-based events only)
- Distributed task ledger sharing across sessions
- Automatic benchmark regression detection in PR CI
- Multi-repository context memory
