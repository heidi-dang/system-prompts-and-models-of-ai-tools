/**
 * Telemetry event types for Phase 1.
 * No network calls. Local JSONL export only.
 */

export interface TelemetryEvent {
  id: string;
  taskId: string;
  type: TelemetryEventType;
  agent?: string;
  timestamp: string;
  payload?: Record<string, unknown>;
}

export type TelemetryEventType =
  | 'task_created'
  | 'task_classified'
  | 'task_executing'
  | 'task_completed'
  | 'task_failed'
  | 'task_blocked'
  | 'delegation_created'
  | 'delegation_completed'
  | 'routing_selected'
  | 'audit_requested'
  | 'audit_completed'
  | 'audit_deduplicated'
  | 'verification_run'
  | 'verification_passed'
  | 'verification_failed'
  | 'retry_attempted'
  | 'retry_blocked'
  | 'circuit_breaker_opened'
  | 'policy_decision'
  | 'checkpoint_saved'
  | 'tool_called'
  | 'error';

/** Phase 2 interfaces — no-op placeholders */
export interface ModelCallObserver {
  observe(): void;
}
export interface BudgetGate {
  check(): { allowed: boolean };
}
export interface TraceExporter {
  export(): void;
}
export interface AdaptiveRouteAdvisor {
  advise(): void;
}
