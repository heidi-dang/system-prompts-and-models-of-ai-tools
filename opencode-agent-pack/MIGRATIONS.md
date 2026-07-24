# Legendary Heidi Migrations

## Version 1.3.0 → 1.4.0

### Changes
- Added native intelligence bridge (composite prompt composition)
- Added modular runtime prompts replacing monolithic prompt
- Added verified memory candidate protocol (replaces direct rules.md mutation)
- Added fast-path execution strategy
- Added failure classifier and circuit breaker
- Added runtime events stream
- Added benchmark infrastructure (Build-vs-Heidi comparison)
- Added runtime doctor
- Added migration support (this file)
- Integrated native explore and general agents
- Upgraded installer with readiness check
- Upgraded uninstall to handle runtime files
- Upgraded rollback to restore runtime state
- Extended CI with runtime compatibility and benchmark smoke

### Migration Steps

```bash
# Check current state
python3 opencode-agent-pack/scripts/migrate.py status

# Apply migration
python3 opencode-agent-pack/scripts/migrate.py apply

# If issues, rollback
python3 opencode-agent-pack/scripts/migrate.py rollback
```

### Manual Steps (if needed)
1. Regenerate prompts: `python3 opencode-agent-pack/scripts/gen-prompts.py`
2. Rebuild context index: `python3 opencode-agent-pack/scripts/context_memory.py index --root . --out .heidi/context-index.json`
3. Run runtime doctor: `./agent.sh --runtime-doctor`
4. Validate all: `./agent.sh --validate-all`

### Breaking Changes
- **Direct memory mutation removed**: Specialists no longer write directly to `.heidi/rules.md`. Use Memory Candidates instead.
- **Agent task allowlist expanded**: Heidi now has `explore` and `general` in its allowlist.
- **Prompt structure changed**: The monolithic prompt is replaced by modular components in `runtime/prompts/`.
- **New runtime files**: `.heidi/runtime-events.jsonl` is now created by the installer.

### Rollback
```bash
./agent.sh --rollback
```
This restores agent definitions, prompts, plugins, config, and runtime policy from the most recent backup.

### Compatibility
- Supported OpenCode versions: >= 0.8.0
- Tested with: 0.12.0
- Plugin API: Not yet available (composite prompt fallback)
- See `opencode-agent-pack/runtime/compatibility.json` for detailed compatibility info.
