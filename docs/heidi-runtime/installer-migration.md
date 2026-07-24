# Installer Migration — Registry Reconciliation

## PR #7 / PR #9 / PR #10 Reconciliation

| PR #7 Change | PR #9 | PR #10 (this PR) | Final Status |
|-------------|-------|-----------------|--------------|
| Remove runtime/ from agent discovery | ✅ Done | ✅ Compatible | ✅ Resolved |
| Backup naming fix (.md.bak → .bak) | ❌ Not done | ❌ Not done | ⬜ Still needed (separate PR) |
| --repair-agent-discovery command | ❌ Not done | ⬜ Handled via runtime doctor | ⬜ Still needed |
| Plugin directory cleanup | ❌ Not done | ⬜ Handled via runtime doctor | ⬜ Still needed |
| XDG_STATE_HOME for runtime files | ❌ Not done | ✅ Configurable via `dbPath` | ✅ Resolved |
| Agent-discovery tests | ❌ Not done | ✅ Via runtime doctor checks | ✅ Partially resolved |
| Backup to private location | ❌ Not done | ❌ Not done | ⬜ Still needed |

## Current Install Layout

```
~/.config/opencode/
  agents/               ← Public agents only
  heidi-runtime/        ← Private runtime files
    runtime.db          ← SQLite runtime database
    prompts/            ← Private prompt fragments
```

## Migration Path

1. `agent.sh --install --global` removes stale `runtime/` dirs
2. Creates `~/.config/opencode/heidi-runtime/` for runtime data
3. Runtime doctor detects and reports stale files
4. No `rm -rf` against uncontrolled paths
5. Preserves custom user agents
