# 🛡️ Repository Rules & Agent Memory

This file serves as the living brain for Heidi AI agents working on this codebase. All custom agents (@heidi, @frontend, @backend, @debugger, @auditor, @planner, @scout) read and enforce these rules.

---

## ⚡ Command Registry (Exact Verification Commands)

Specify exact verification commands for this repository so agents execute them without guessing:

- **Typecheck Command**: `[e.g. pnpm tsc --noEmit / npx tsc --noEmit / cargo check]`
- **Lint Command**: `[e.g. pnpm lint / npm run lint / ruff check .]`
- **Test Command**: `[e.g. pnpm test / pytest / cargo test]`
- **Build Command**: `[e.g. pnpm build / npm run build / cargo build]`

---

## 🏗️ Architecture & Conventions

### Stack & Framework Constraints
- **Primary Framework**: `[e.g. Next.js App Router / Vite React / FastAPI / Go]`
- **Styling**: `[e.g. Tailwind CSS utility classes with shadcn/ui components]`
- **State Management**: `[e.g. React Server Components + SWR / Zustand / Redux]`
- **Database / ORM**: `[e.g. Prisma ORM with PostgreSQL / Drizzle / SQLAlchemy]`

### Directory Layout & Boundaries
- `src/components/` — Reusable UI components (keep under 200 lines).
- `src/app/` / `src/pages/` — Page routes and API endpoints.
- `src/lib/` — Shared utilities, database client, and helper functions.

---

## 🚫 Repository Gotchas & Anti-Patterns

- **DO NOT** use inline CSS styles when Tailwind classes exist.
- **DO NOT** bypass authentication middleware on API routes.
- **DO NOT** edit database migration files after they have been applied.
- **DO NOT** disable linter or TypeScript rules without explaining why in a comment.

---

## 🧠 Agent Memory & Past Learnings

*Agents automatically record learned gotchas, user preferences, and tricky bug resolutions here so future sessions never repeat mistakes.*

- [2026-07-23] **Initial Memory System Online**: `.heidi/rules.md` registered as repository memory.
