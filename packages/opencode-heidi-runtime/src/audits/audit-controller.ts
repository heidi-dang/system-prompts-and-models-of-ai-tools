/**
 * Audit controller — one task-level audit deduplication.
 */

import { randomUUID } from 'crypto';
import { RuntimeDatabase } from '../storage/database.js';
import { createHash } from 'crypto';

export type AuditTriggerSource = 'user_request' | 'routing_decision' | 'security_policy' | 'production_sensitivity' | 'verification_policy';

export interface AuditRequest {
  taskId: string;
  triggerSource: AuditTriggerSource;
  scope: string;         // Canonical scope hash-key
  description: string;
}

export interface AuditResult {
  allowed: boolean;
  reason: string;
  existingAuditId?: string;
  isDeduplicated: boolean;
}

export class AuditController {
  constructor(private db: RuntimeDatabase) {}

  /**
   * Request an audit. Returns the audit result.
   * Deduplicates equivalent audits via scope hash.
   */
  requestAudit(request: AuditRequest): AuditResult {
    const scopeHash = createHash('sha256')
      .update(`${request.taskId}:${request.scope}`)
      .digest('hex')
      .slice(0, 16);

    // Check for existing completed audit with same scope
    const existingCompleted = this.db.connection.prepare(`
      SELECT id, status FROM audit_runs
      WHERE task_id = ? AND scope_hash = ? AND status = 'completed'
      ORDER BY created_at DESC LIMIT 1
    `).get(request.taskId, scopeHash) as { id: string; status: string } | undefined;

    if (existingCompleted) {
      return {
        allowed: true,  // Audit was done — result is available
        reason: 'audit completed for this scope, reusing result',
        existingAuditId: existingCompleted.id,
        isDeduplicated: true,
      };
    }

    // Check for existing pending audit with same scope
    const existingPending = this.db.connection.prepare(`
      SELECT id, status FROM audit_runs
      WHERE task_id = ? AND scope_hash = ?
      ORDER BY created_at DESC LIMIT 1
    `).get(request.taskId, scopeHash) as { id: string; status: string } | undefined;

    if (existingPending) {
      return {
        allowed: true,
        reason: 'audit already pending for this scope',
        existingAuditId: existingPending.id,
        isDeduplicated: true,
      };
    }

    // Count existing audit runs for this task
    const existingCount = this.db.connection.prepare(`
      SELECT COUNT(*) as count FROM audit_runs WHERE task_id = ?
    `).get(request.taskId) as { count: number };

    // maxAuditCycles is 1 in Phase 1
    if (existingCount.count >= 1 && request.triggerSource !== 'user_request') {
      return {
        allowed: false,
        reason: 'maximum audit cycles reached for this task',
        isDeduplicated: false,
      };
    }

    // Create new audit record
    const id = `audit_${randomUUID().slice(0, 8)}`;
    this.db.connection.prepare(`
      INSERT INTO audit_runs (id, task_id, trigger_source, scope_hash, status)
      VALUES (?, ?, ?, ?, 'pending')
    `).run(id, request.taskId, request.triggerSource, scopeHash);

    return {
      allowed: true,
      reason: `new audit created (${request.triggerSource})`,
      existingAuditId: id,
      isDeduplicated: false,
    };
  }

  /** Check whether an audit is needed for a given task scope */
  isAuditNeeded(taskId: string, scope: string): boolean {
    const scopeHash = createHash('sha256')
      .update(`${taskId}:${scope}`)
      .digest('hex')
      .slice(0, 16);

    const existing = this.db.connection.prepare(`
      SELECT COUNT(*) as count FROM audit_runs
      WHERE task_id = ? AND scope_hash = ?
    `).get(taskId, scopeHash) as { count: number };

    return existing.count === 0;
  }
}
