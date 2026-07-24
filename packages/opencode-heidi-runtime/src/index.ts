/**
 * Heidi Core Runtime Plugin — entry point.
 *
 * Exports the OpenCode plugin factory and all public types.
 * Phase 1: offline-capable deterministic runtime foundation.
 */

export { heidiRuntimePlugin } from './plugin.js';
export type { HeidiRuntimeConfig, HeidiRuntimeOptions, Phase2Placeholder } from './config/schema.js';

// Public type exports
export type {
  TaskStatus,
  TaskRecord,
  Strategy,
  RoutingDecision,
  DelegationContract,
  OwnershipBoundary,
  PolicyDecision,
  VerificationRecord,
  AuditRecord,
  RetryFingerprint,
} from './lifecycle/state-machine.js';
