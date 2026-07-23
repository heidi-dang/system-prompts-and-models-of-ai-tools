# 🛡️ Repository Rules & Agent Memory

This file serves as the living brain for Heidi AI agents working on this codebase. All custom agents (@heidi, @frontend, @backend, @debugger, @auditor, @planner, @scout) read and enforce these rules.

---

## ⚡ Command Registry (Exact Verification Commands)

Specify exact verification commands for this repository so agents execute them without guessing:

- **Typecheck Command**: `bash -n agent.sh`
- **Lint Command**: `./agent.sh --check`
- **Test Command**: `./agent.sh --doctor`
- **Build Command**: `./agent.sh --both`

---

## 🏗️ Architecture & Conventions

### Stack & Framework Constraints
- **Primary Framework**: Bash Shell Scripts + OpenCode Agent Markdown Pack
- **Agent Registry**: `.opencode/agents/*.md` and `~/.config/opencode/agents/*.md`
- **Installation Tool**: `agent.sh` with `--both`, `--global`, `--project`, `--repair`, `--init-rules`

---

## 🚫 Repository Gotchas & Anti-Patterns

- **DO NOT** edit agent prompts without updating frontmatter YAML (`description`, `mode`, `temperature`, `permission`).
- **DO NOT** remove Reasoning Protocol or Anti-Patterns sections from agent prompts.
- **DO NOT** omit python3 check when editing JSON configuration functions in `agent.sh`.

---

## 🧠 Agent Memory & Past Learnings

*Agents automatically record learned gotchas, user preferences, and tricky bug resolutions here so future sessions never repeat mistakes.*

- [2026-07-23] **Initial Memory System Online**: `.heidi/rules.md` registered as repository memory.
- [2026-07-23] **Git Authentication**: Remote URL configured with PAT for seamless `git push origin main`.
