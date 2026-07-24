# Context Engine (Phase 1)

## Design

Bounded context retrieval with provenance tracking.

## Rules

1. Never send full conversation to subagent by default
2. Never send full repository map when focused pack is enough
3. Cache file hashes, avoid rereading unchanged files
4. Mark stale facts
5. Record why each item was included
6. Cap pack size (default: 8,000 chars)
7. Prefer source file provenance over generated summaries
8. Redact secrets in stored context
9. Phase 2: cache/index optimization

## Context Pack

```typescript
interface ContextPack {
  objective: string;
  successCriteria: string[];
  selectedFiles: string[];
  relevantExcerpts: string[];
  repositoryRules: string[];
  verificationCommands: string[];
  provenance: string[];
  charCount: number;
}
```

## Benchmark Targets

- 50% reduction in repeated file reads vs. no runtime
- 50% reduction in delegation context size
- No reduction in benchmark correctness
