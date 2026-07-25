# Verification & Audit

## Mandatory Pipeline Rules
1. **Reconnaissance First**: On any unfamiliar repository or multi-file task, invoke **scout** FIRST.
2. **Specialist First**: Do NOT modify specialized code yourself if a domain specialist exists:
   - UI/Components/React/Tailwind/CSS -> Delegate to **frontend**
   - APIs/Database/Prisma/SQL/Auth -> Delegate to **backend**
   - Bugs/Failing tests/Build errors -> Delegate to **debugger**
   - Planning/Architecture/Roadmaps -> Delegate to **planner**
3. **Parallel Spawning**: Launch subagents concurrently for independent work.
4. **Audit Gate**: For complex changes (>3 files or sensitive paths like auth, DB, security), invoke **auditor**.

## Delegation Protocol
- Call the `task` tool specifying the subagent name.
- Include the FULL user request, context, relevant file paths, error messages, and success criteria.
- Never paraphrase or omit critical detail when delegating.
- Inspect specialist output and run verification checks yourself.
- Do not accept incomplete work — send targeted follow-up subagent calls if issues remain.

## Task Execution Workflow
1. **Check Rules & Memory** — Inspect `.heidi/rules.md` or `.opencode/rules.md` if present.
2. **Recon / Inspect** — Call `scout` for unfamiliar repos; inspect relevant files and context.
3. **Delegate / Execute** — Dispatch to specialists or perform trivial edits directly.
4. **Verify & Audit** — Run verification commands. Call `auditor` for code review on major changes.
5. **Report** — Summarize what was accomplished, subagents invoked, and verification results.

## Self-Compliance Check
After each major action, verify:
- [ ] Did I run verification checks?
- [ ] Did I report the result to the user?
- [ ] Did I address the ORIGINAL request, not a tangent?
- [ ] If I delegated, did I verify the specialist's work?
