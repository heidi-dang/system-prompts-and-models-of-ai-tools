# Phase 2 Contract — Deferred Interfaces

The following interfaces exist in Phase 1 as no-op placeholders.
They do not enforce provider-level limits in Phase 1.

## Interfaces

```typescript
interface ModelCallObserver {
  observe(): void;
  // Phase 2: record model call, tokens, cost
}

interface BudgetGate {
  check(): { allowed: boolean };
  // Phase 2: enforce budget before provider dispatch
}

interface BudgetReservation {
  reserve(): boolean;
  // Phase 2: atomic budget reservation
}

interface UsageReconciler {
  reconcile(): void;
  // Phase 2: reconcile provider-reported vs estimated usage
}

interface PricingResolver {
  resolve(model: string): { inputPer1k: number; outputPer1k: number };
  // Phase 2: model pricing lookup
}

interface TraceExporter {
  export(): void;
  // Phase 2: structured trace export
}

interface AdaptiveRouteAdvisor {
  advise(): void;
  // Phase 2: adaptive routing from historical outcomes
}
```

## Budget Gate Status (Phase 1)

```json
{
  "mode": "advisory",
  "provider_boundary_enforced": false,
  "hard_limit_available": false,
  "phase": 2
}
```

Provider-boundary token enforcement is deferred to Phase 2.
