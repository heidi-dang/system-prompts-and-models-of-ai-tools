import { describe, it, expect, beforeEach } from 'vitest';
import { RuntimeDatabase } from '../../src/storage/database.js';
import { AuditController } from '../../src/audits/audit-controller.js';
import { tmpdir } from 'os';
import { join } from 'path';
import { randomUUID } from 'crypto';

function makeDb(): RuntimeDatabase {
  return new RuntimeDatabase(join(tmpdir(), `heidi-test-${randomUUID().slice(0, 8)}.db`));
}

function createTask(db: RuntimeDatabase, id: string): void {
  db.connection.prepare(
    `INSERT OR IGNORE INTO tasks (id, objective, status) VALUES (?, ?, 'created')`
  ).run(id, `test task ${id}`);
}

describe('AuditController', () => {
  let db: RuntimeDatabase;
  let controller: AuditController;

  beforeEach(() => {
    db = makeDb();
    controller = new AuditController(db);
    createTask(db, 'task-1');
  });

  it('creates first audit for a new scope', () => {
    const r = controller.requestAudit({
      taskId: 'task-1',
      triggerSource: 'routing_decision',
      scope: 'auth-module-review',
      description: 'review the auth module',
    });
    expect(r.allowed).toBe(true);
    expect(r.isDeduplicated).toBe(false);
    expect(r.existingAuditId).toBeDefined();
  });

  it('deduplicates equivalent scope audits', () => {
    const first = controller.requestAudit({
      taskId: 'task-1',
      triggerSource: 'routing_decision',
      scope: 'auth-module-review',
      description: 'review the auth module',
    });

    // Mark as completed
    db.connection.prepare(
      `UPDATE audit_runs SET status = 'completed' WHERE id = ?`
    ).run(first.existingAuditId!);

    const second = controller.requestAudit({
      taskId: 'task-1',
      triggerSource: 'security_policy',
      scope: 'auth-module-review',
      description: 'also review the auth module',
    });
    expect(second.allowed).toBe(true);
    expect(second.isDeduplicated).toBe(true);
    expect(second.existingAuditId).toBe(first.existingAuditId);
  });

  it('blocks automatic audit after max cycles with different scope', () => {
    // First audit (routing_decision)
    controller.requestAudit({
      taskId: 'task-1',
      triggerSource: 'routing_decision',
      scope: 'scope-1',
      description: 'first audit',
    });

    // Second automatic audit (different scope) — should be blocked
    const second = controller.requestAudit({
      taskId: 'task-1',
      triggerSource: 'security_policy',
      scope: 'scope-2',
      description: 'second audit different scope',
    });
    expect(second.allowed).toBe(false);
    expect(second.reason).toContain('maximum audit cycles');
  });

  it('allows user-requested audit even after automatic audit', () => {
    controller.requestAudit({
      taskId: 'task-1',
      triggerSource: 'routing_decision',
      scope: 'scope-1',
      description: 'automatic audit',
    });

    const userRequest = controller.requestAudit({
      taskId: 'task-1',
      triggerSource: 'user_request',
      scope: 'scope-1',
      description: 'user requested audit',
    });
    expect(userRequest.allowed).toBe(true);
  });

  it('reports audit needed correctly', () => {
    expect(controller.isAuditNeeded('task-1', 'new-scope')).toBe(true);

    controller.requestAudit({
      taskId: 'task-1',
      triggerSource: 'routing_decision',
      scope: 'new-scope',
      description: '',
    });

    expect(controller.isAuditNeeded('task-1', 'new-scope')).toBe(false);
  });
});
