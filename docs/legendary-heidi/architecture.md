# Legendary Heidi Architecture

## What "Legendary" Means
Legendary Heidi does not mean unrestricted autonomy or guaranteed superiority.
It means that Heidi is:
- model-aware — composes with native model intelligence
- repository-aware — uses context memory and repository fingerprinting
- strategy-driven — selects explicit strategies per task
- measurable — benchmarked against Build with deterministic grading
- bounded — circuit breakers, retry limits, escalation rules
- auditable — task ledger, runtime events, proactive audit
- reversible — rollback, uninstall, migration paths
- empirically evaluated — benchmark scores are from actual runs, not claims

## Core Components

### 1. Native Intelligence Bridge
- Composite prompt generation preserves provider-specific instructions
- Runtime doctor validates composition integrity
- No hardcoded model IDs or provider names

### 2. Modular Orchestration Prompt
- core.md: identity, reasoning, tool usage, conventions
- routing.md: agent routing, native agent policy, delegation rules
- orchestration.md: strategy selection, parallel execution, handoffs
- memory.md: rule precedence, verified memory protocol, context injection
- verification.md: pipeline rules, delegation protocol, compliance checks
- resilience.md: error recovery, circuit breaker, environment handling
- reporting.md: progress updates, context management, anti-patterns
- fast-path.md: fast path conditions and escalation rules

### 3. Runtime Scripts
- context_memory.py: context index creation, search, staleness, retrieval
- strategy_selector.py: deterministic strategy selection with fast path
- task_ledger.py: durable task tracking with recovery
- memory.py: verified memory candidates and promotion
- prompt_proposals.py: prompt evolution state machine
- proactive_audit.py: triggered audit checks
- failure_classifier.py: failure categorization and retry policies
- runtime_events.py: observable event stream
- runtime_doctor.py: runtime diagnostics
- migrate.py: version migration
- benchmark.py: Build-vs-Heidi comparison
- gen-prompts.py: modular prompt generation

### 4. Agent Definitions
- heidi.md: primary orchestrator with native agent routing
- scout.md: repository reconnaissance with memory candidates
- frontend.md: UI specialist with memory candidates
- backend.md: API/database specialist with memory candidates
- debugger.md: debugging specialist with memory candidates
- auditor.md: read-only audit specialist with memory candidates
- planner.md: planning specialist with memory candidates

### 5. Infrastructure
- agent.sh: installer, doctor, benchmark, migrate, uninstall, rollback
- CI: static analysis, installer matrix, runtime compatibility, benchmark smoke
- Benchmarks: deterministic grading, task categories, Build-vs-Heidi comparison

## Limitations
- Plugin API not yet available; composite prompt used as workaround
- Token/tool metrics not exposed by OpenCode
- Real-model benchmarks require opt-in workflow
- Session-level hooks not available for automatic task ledger start
