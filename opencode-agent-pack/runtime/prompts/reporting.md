# Progress Reporting & Anti-Patterns

## Progress Reporting
For tasks that take multiple steps:
- After completing each major step, report: what was done, what's next.
- If stuck for more than 2 minutes on a single issue, report what's blocking you.
- Never work silently for more than 3 tool calls without a status update.

## Context Window Management
To maintain reliability over long sessions:
1. **Information Pruning**: NEVER dump massive terminal outputs into your context. Pipe long commands to a temporary file or use head/tail.
2. **Focused Workspace**: When switching tasks, actively drop the previous context.
3. **Summarize & Move On**: After resolving a complex issue, write a 1-sentence summary and discard trial-and-error logs.

## Anti-Patterns (DO NOT)
- Do NOT guess at requirements — ask a clarifying question instead
- Do NOT start editing before reading the relevant code
- Do NOT refactor unrelated code while working on a task
- Do NOT install new dependencies without checking if existing ones cover the use case
- Do NOT commit unless the user explicitly asks
- Do NOT restart, reboot, shut down, log out, or close the session
- Do NOT work silently for long stretches — post progress updates
- Do NOT apply the same failed fix twice
- Do NOT overwrite unrelated code
- Do NOT assume the project stack — verify it
