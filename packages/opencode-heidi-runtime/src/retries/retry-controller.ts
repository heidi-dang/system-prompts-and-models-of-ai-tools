/**
 * Retry controller — bounded retries with circuit breaker.
 */

import { randomUUID } from 'crypto';
import { RuntimeDatabase } from '../storage/database.js';
import { hashFingerprint, fingerprintChanged } from './fingerprint.js';
import type { RetryFingerprint } from '../lifecycle/state-machine.js';

export interface RetryDecision {
  allowed: boolean;
  attempt: number;
  reason: string;
  existingFingerprint?: string;
}

export class RetryController {
  constructor(private db: RuntimeDatabase) {}

  /**
   * Evaluate whether a retry is allowed.
   * Returns allowed=true if no equivalent failure fingerprint exists.
   * Blocks after maxEquivalentRetries (default: 2).
   */
  evaluateRetry(taskId: string, fingerprint: RetryFingerprint, maxRetries: number = 2): RetryDecision {
    const fpHash = hashFingerprint(fingerprint);

    // Check if this exact fingerprint exists
    const existing = this.db.connection.prepare(`
      SELECT attempt FROM retry_fingerprints WHERE task_id = ? AND fingerprint = ?
    `).get(taskId, fpHash) as { attempt: number } | undefined;

    if (existing) {
      if (existing.attempt > maxRetries) {
        return {
          allowed: false,
          attempt: existing.attempt,
          reason: 'circuit breaker: max equivalent retries reached',
          existingFingerprint: fpHash,
        };
      }
      // Increment attempt count
      this.db.connection.prepare(`
        UPDATE retry_fingerprints SET attempt = attempt + 1 WHERE task_id = ? AND fingerprint = ?
      `).run(taskId, fpHash);
      const newAttempt = this.db.connection.prepare(
        `SELECT attempt FROM retry_fingerprints WHERE task_id = ? AND fingerprint = ?`
      ).get(taskId, fpHash) as { attempt: number };

      return {
        allowed: newAttempt.attempt <= maxRetries,
        attempt: newAttempt.attempt,
        reason: newAttempt.attempt <= maxRetries
          ? `retry ${newAttempt.attempt}/${maxRetries}`
          : 'circuit breaker: max retries reached',
        existingFingerprint: fpHash,
      };
    }

    // First occurrence — record and allow
    this.db.connection.prepare(`
      INSERT INTO retry_fingerprints (id, task_id, fingerprint, attempt, strategy)
      VALUES (?, ?, ?, 1, ?)
    `).run(`rf_${randomUUID().slice(0, 8)}`, taskId, fpHash, fingerprint.strategy);

    return { allowed: true, attempt: 1, reason: 'first attempt' };
  }

  /** Check if a fingerprint change is material */
  isMaterialChange(previous: RetryFingerprint, current: RetryFingerprint): boolean {
    return fingerprintChanged(previous, current);
  }
}
