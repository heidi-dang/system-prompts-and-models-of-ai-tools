# OpenCode Runtime Audit

## Installed Version
Not installed in CI environment

## Native Prompt Resolution
OpenCode selects provider-specific system prompts based on the configured model.
When a custom agent definition exists:
- The agent's markdown content (after YAML frontmatter) becomes the system prompt
- This REPLACES the native provider-specific prompt by default
- Legendary Heidi addresses this by providing a composite prompt approach

## Custom Agent Prompt Behaviour
- Agent definitions in `.opencode/agents/` or global config are loaded
- YAML frontmatter configures: mode (primary/subagent), temperature, permissions
- The body after `---` becomes the system prompt text
- No native hook exists (as of tested version) to "append" to the native prompt
- Workaround: composite prompt generation with native prompt preservation check

## Plugin Discovery
- OpenCode plugin system: not yet available in tested version
- Custom plugins are not yet a documented extension point
- Legendary Heidi implements plugin-like configuration in `opencode-agent-pack/plugins/`
  for future compatibility, but uses composite prompt generation as the active approach

## Available Hooks
- No documented hook system found in the tested OpenCode version
- Task lifecycle: only tool-level hooks (bash, edit, task permissions)
- No pre/post-task hooks available

## Session Lifecycle Events
- Session start: model selection triggers provider prompt loading
- Session events: not exposed to custom plugins
- Task completion: no hook available for post-task processing

## Tool Lifecycle Events
- Each tool has permission configuration (allow/deny)
- Task tool has an allowlist per agent
- No pre/post tool hooks available

## Agent and Model Metadata
- Agent name, mode, temperature available in frontmatter
- Model metadata: model ID known at runtime but not exposed to agent prompt
- Session ID: not exposed

## Native Agent Availability
- Build agent (native)
- Plan agent (native)
- Explore agent (native, conditional)
- General agent (native, conditional)
- Custom agents (via agent definitions)

## Chosen Integration Architecture
Since OpenCode's plugin API is not yet available:
1. Heidi preserves OpenCode's native provider prompt through composite prompt generation
2. The generation script (`gen-prompts.py`) creates prompts that do not overwrite native instructions
3. Runtime doctor validates native prompt composition on every install
4. When a plugin API becomes available, the plugin files in `plugins/` provide the bridge

## Unsupported Capabilities
- Real-time session hooks
- Token/tool usage metrics exposure
- Model-level prompt composition (no native append mode)
- Session ID exposure to agent prompts
- Agent definition inheritance/extension

## Compatibility Risks
- OpenCode updates may change provider prompt format → validated by runtime doctor
- New model families may require prompt updates → no hardcoded model IDs
- Plugin API introduction may require adapter → plugins/ directory prepared
- Agent frontmatter schema changes → validate_agents.py catches regressions
