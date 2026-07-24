import { describe, it, expect } from 'vitest';
import { RuntimeDatabase } from '../../src/storage/database.js';
import { tmpdir } from 'os';
import { join } from 'path';
import { randomUUID } from 'crypto';

describe('RuntimeDatabase', () => {
  it('creates database and runs migrations', () => {
    const path = join(tmpdir(), `heidi-test-${randomUUID().slice(0, 8)}.db`);
    const db = new RuntimeDatabase(path);
    expect(db.dbPath).toBe(path);

    // Verify tables exist
    const tables = db.connection.prepare(
      `SELECT name FROM sqlite_master WHERE type='table' ORDER BY name`
    ).all() as { name: string }[];
    const tableNames = tables.map(t => t.name);
    expect(tableNames).toContain('tasks');
    expect(tableNames).toContain('sessions');
    expect(tableNames).toContain('events');
    expect(tableNames).toContain('delegations');
    expect(tableNames).toContain('routing_decisions');
    expect(tableNames).toContain('audit_runs');
    expect(tableNames).toContain('retry_fingerprints');
    expect(tableNames).toContain('verification_runs');
    expect(tableNames).toContain('checkpoints');
    expect(tableNames).toContain('context_items');
    expect(tableNames).toContain('policy_decisions');
    expect(tableNames).toContain('budget_interfaces');
    expect(tableNames).toContain('runtime_meta');

    // Verify schema version
    const version = db.connection.prepare(
      `SELECT value FROM runtime_meta WHERE key = 'schema_version'`
    ).get() as { value: string };
    expect(version.value).toBe('1');

    db.close();
  });

  it('passes integrity check', () => {
    const path = join(tmpdir(), `heidi-test-${randomUUID().slice(0, 8)}.db`);
    const db = new RuntimeDatabase(path);
    expect(db.checkIntegrity()).toBeNull();
    db.close();
  });

  it('supports concurrent writes safely via WAL', () => {
    const path = join(tmpdir(), `heidi-test-${randomUUID().slice(0, 8)}.db`);
    const db = new RuntimeDatabase(path);

    // Insert and read back
    db.connection.prepare(`
      INSERT INTO tasks (id, objective, status) VALUES (?, ?, ?)
    `).run('test-task-1', 'concurrent test', 'created');

    const row = db.connection.prepare(`SELECT id FROM tasks WHERE id = ?`).get('test-task-1') as { id: string };
    expect(row.id).toBe('test-task-1');

    db.close();
  });

  it('rolls back invalid transaction', () => {
    const path = join(tmpdir(), `heidi-test-${randomUUID().slice(0, 8)}.db`);
    const db = new RuntimeDatabase(path);

    expect(() => {
      db.connection.exec('BEGIN; INSERT INTO nonexistent VALUES (1); COMMIT;');
    }).toThrow();

    db.close();
  });
});
