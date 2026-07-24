# Heidi Core Runtime Plugin — Architecture

## Overview

The Heidi Core Runtime is an OpenCode-native plugin that replaces optional prompt compliance and manually invoked Python scripts with deterministic runtime behavior.

## Package Structure

```
packages/opencode-heidi-runtime/
├── src/
│   ├── index.ts                   Public exports
│   ├── plugin.ts                  OpenCode plugin entry point
│   ├── config/                    Schema, defaults, loader
│   ├── lifecycle/                 Task manager, state machine, session mapper
│   ├── routing/                   Classifier, signal extraction, strategy selection
│   ├── context/                   Repository index, context selection, packs
│   ├── delegation/                Contracts, ownership, delegate tool
│   ├── governance/                Policy engine, command policy, redaction
│   ├── retries/                   Fingerprinting, retry controller, circuit breaker
│   ├── audits/                    Audit controller, deduplication
│   ├── verification/              Engine, completion gate, planner
│   ├── storage/                   SQLite database, migrations
│   ├── telemetry/                 Event bus, metrics, Phase 2 interfaces
│   ├── tools/                     Custom OpenCode tools
│   ├── doctor/                    Runtime checks, report, repair
│   └── compatibility/             Legacy Python adapter, versioning
```

## Key Principles

1. **Direct execution is the default.** Delegation only when justified.
2. **Deterministic routing.** Weighted signal matching, no substring false triggers.
3. **SQLite persistence.** Transctional, WAL mode, schema-versioned.
4. **Plugin hooks over prompt compliance.** Lifecycle, governance, and telemetry are enforced by code, not requested by prompt.
5. **Phase 2 interfaces exist without false claims.** Budget gate reports `mode: advisory`, not enforced.
