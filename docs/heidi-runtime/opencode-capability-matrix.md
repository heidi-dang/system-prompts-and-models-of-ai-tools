# OpenCode Plugin API Capability Matrix

OpenCode version: 1.18.4 (plugin package)
Inspection date: 2026-07-24
Source: `@opencode-ai/plugin@1.18.4` type definitions

## Phase 1 Feature Mapping

| Feature | Hook / Mechanism | Status | Notes |
|---------|-----------------|--------|-------|
| Register custom tools | `tool` hook | ✅ Native | Direct tool definition registration |
| Task lifecycle tracking | `event` hook | ✅ Native | All runtime events observable |
| Lifecycle init/config | `config` hook | ✅ Native | Plugin receives config on init |
| Governance: command policy | `command.execute.before` | ✅ Native | Can inspect/modify commands before exec |
| Governance: tool policy | `tool.execute.before` | ✅ Native | Can inspect/modify tool args before exec |
| Governance: permission | `permission.ask` | ✅ Native | Can allow/deny/ask permission requests |
| Inject system prompt | `experimental.chat.system.transform` | ✅ Native | Can add runtime instructions to system prompt |
| Modify LLM parameters | `chat.params` | ✅ Native | Control temp, topP, max tokens |
| Session compaction control | `experimental.session.compacting` | ✅ Native | Customize compaction behavior |
| Capture tool results | `tool.execute.after` | ✅ Native | Access tool output after execution |
| Detect message start/end | `chat.message` | ✅ Native | New message event |
| Shell env customization | `shell.env` | ✅ Native | Per-session/call env vars |
| Transform messages | `experimental.chat.messages.transform` | ✅ Native | Modify conversation messages |
| Provider/model discovery | `provider` hook | ✅ Native | Register custom models |
| Auth flows | `auth` hook | ✅ Native | OAuth, API key management |

## Phase 2 Feature Mapping

| Feature | Hook Status | Plan |
|---------|------------|------|
| Block model request before dispatch | `chat.params` (partial) | Can modify params but not prevent dispatch; may need provider wrapper or `chat.headers` manipulation |
| Parent-child lineage from plugin | `event` hook | Session/agent IDs available in events |
| Shared state across processes | SQLite (plugin-managed) | Plugin manages its own DB; not through OpenCode API |
| Budget enforcement before provider call | No direct hook | Use custom provider registration or gateway in Phase 2 |
| Token usage from provider | No direct hook exposed | Must capture from provider response in Phase 2 |
| Real progress events | No `progress` hook | Must use custom tools or event-driven patterns |

## Legend

- ✅ Native — directly supported by the plugin API
- 🟡 Partial — works but requires workarounds or has limitations
- ❌ Not supported — no hook exists; deferred to Phase 2
