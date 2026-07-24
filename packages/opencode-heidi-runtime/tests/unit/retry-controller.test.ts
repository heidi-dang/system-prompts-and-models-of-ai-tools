import { describe, it, expect, beforeEach } from 'vitest';
import { RuntimeDatabase } from '../../src/storage/database.js';
import { RetryController } from '../../src/retries/retry-controller.js';
import type { RetryFingerprint } from '../../src/lifecycle/state-machine.js';
import { tmpdir } from 'os';
import { join } from 'path';
import { randomUUID } from 'crypto';

function makeDb(): RuntimeDatabase {
  return new RuntimeDatabase(join(tmpdir(), `heidi-test-${randomUUID().slice(0, 8)}.db`));
}

function makeFingerprint(overrides: Partial<RetryFingerprint> = {}): RetryFingerprint {
  return {
    taskObjective: 'fix bug',
    strategy: 'direct',
    agent: 'heidi',
    toolOrCommand: 'edit',
    files: ['src/index.ts'],
    normalizedError: 'TypeError: undefined is not a function',
    contextHash: 'abc123',
    environmentSignature: 'node20',
    ...overrides,
  };
}

function createTask(db: RuntimeDatabase, id: string): void {
  db.connection.prepare(
    `INSERT OR IGNORE INTO tasks (id, objective, status) VALUES (?, ?, 'created')`
  ).run(id, `test task ${id}`);
}

describe('RetryController', () => {
  let db: RuntimeDatabase;
  let controller: RetryController;

  beforeEach(() => {
    db = makeDb();
    controller = new RetryController(db);
    createTask(db, 'task-1');
  });

  it('allows first attempt', () => {
    const d = controller.evaluateRetry('task-1', makeFingerprint());
    expect(d.allowed).toBe(true);
    expect(d.attempt).toBe(1);
  });

  it('allows second attempt for equivalent failure', () => {
    const fp = makeFingerprint();
    controller.evaluateRetry('task-1', fp);
    const d = controller.evaluateRetry('task-1', fp);
    expect(d.allowed).toBe(true);
    expect(d.attempt).toBe(2);
  });

  it('blocks third equivalent attempt (circuit breaker)', () => {
    const fp = makeFingerprint();
    controller.evaluateRetry('task-1', fp);
    controller.evaluateRetry('task-1', fp);
    const d = controller.evaluateRetry('task-1', fp);
    expect(d.allowed).toBe(false);
    expect(d.reason).toContain('circuit breaker');
  });

  it('allows first attempt for different fingerprint', () => {
    controller.evaluateRetry('task-1', makeFingerprint({ toolOrCommand: 'read' }));
    const d = controller.evaluateRetry('task-1', makeFingerprint({ toolOrCommand: 'edit' }));
    expect(d.allowed).toBe(true);
    expect(d.attempt).toBe(1);
  });

  it('detects material change in fingerprint', () => {
    const a = makeFingerprint({ toolOrCommand: 'edit', files: ['a.ts'] });
    const b = makeFingerprint({ toolOrCommand: 'edit', files: ['b.ts'] });
    expect(controller.isMaterialChange(a, b)).toBe(true);
  });

  it('detects no material change for identical fingerprints', () => {
    const a = makeFingerprint();
    const b = makeFingerprint();
    expect(controller.isMaterialChange(a, b)).toBe(false);
  });
});
