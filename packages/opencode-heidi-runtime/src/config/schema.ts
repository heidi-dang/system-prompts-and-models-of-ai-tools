import { z } from 'zod';

/**
 * Phase 1 runtime configuration schema.
 * Phase 2 fields are marked as placeholders.
 */

export const HeidiRuntimeOptions = z.object({
  /** Path to the SQLite runtime database. Default: ~/.config/opencode/heidi-runtime/runtime.db */
  dbPath: z.string().optional(),

  /** Maximum context pack size in characters */
  maxContextChars: z.number().int().positive().default(8000),

  /** Maximum delegation depth (Phase 1: always 1) */
  maxDelegationDepth: z.literal(1).default(1),

  /** Maximum parallel subagents (Phase 1: 0 or 2) */
  maxParallelAgents: z.number().int().min(0).max(2).default(2),

  /** Maximum retry attempts for equivalent failures */
  maxEquivalentRetries: z.number().int().min(0).max(3).default(2),

  /** Maximum audit cycles per task */
  maxAuditCycles: z.literal(1).default(1),

  /** Enable telemetry recording */
  telemetryEnabled: z.boolean().default(true),

  /** Telemetry retention in days */
  telemetryRetentionDays: z.number().int().positive().default(30),

  /** Verbose logging */
  verbose: z.boolean().default(false),

  /**
   * Phase 2: Provider budget placeholder.
   * In Phase 1, this is advisory-only and does not enforce provider-level limits.
   */
  _phase2Budget: z.object({
    enabled: z.literal(false).default(false),
    maxTokensPerTask: z.number().int().positive().default(1_500_000),
    maxCostPerTask: z.number().positive().default(50.0),
  }).optional().default({ enabled: false }),
});

export type HeidiRuntimeConfig = z.infer<typeof HeidiRuntimeOptions>;

export type Phase2Placeholder = {
  /** Phase 2 integration marker */
  phase: 2;
  /** Budget gate is not active in Phase 1 */
  providerBoundaryEnforced: false;
  /** No hard limits available */
  hardLimitAvailable: false;
  /** Advisory mode only */
  mode: 'advisory';
};

export const DEFAULT_CONFIG: HeidiRuntimeConfig = HeidiRuntimeOptions.parse({});
