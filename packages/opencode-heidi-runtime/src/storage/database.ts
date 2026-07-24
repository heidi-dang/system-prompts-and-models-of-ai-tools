import Database from 'better-sqlite3';
import { existsSync, mkdirSync } from 'fs';
import { dirname } from 'path';

export class RuntimeDatabase {
  private db: Database.Database;
  public readonly dbPath: string;

  constructor(dbPath: string) {
    const dir = dirname(dbPath);
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }
    this.dbPath = dbPath;
    this.db = new Database(dbPath);
    this.db.pragma('journal_mode = WAL');
    this.db.pragma('foreign_keys = ON');
    this.db.pragma('busy_timeout = 5000');
    this.runMigrations();
  }

  get connection(): Database.Database {
    return this.db;
  }

  /** Run all pending migrations in a transaction */
  private runMigrations(): void {
    const version = this.getSchemaVersion();
    if (version < 1) {
      this.migrateV1();
    }
    // Future: if (version < 2) { this.migrateV2(); }
  }

  private getSchemaVersion(): number {
    try {
      const row = this.db.prepare(
        `SELECT value FROM runtime_meta WHERE key = 'schema_version'`
      ).get() as { value: string } | undefined;
      return row ? parseInt(row.value, 10) : 0;
    } catch {
      return 0;
    }
  }

  private migrateV1(): void {
    this.db.exec(`BEGIN TRANSACTION;

      CREATE TABLE IF NOT EXISTS runtime_meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
      );

      INSERT OR IGNORE INTO runtime_meta (key, value) VALUES ('schema_version', '1');

      CREATE TABLE IF NOT EXISTS tasks (
        id               TEXT PRIMARY KEY,
        session_id       TEXT,
        objective        TEXT NOT NULL,
        status           TEXT NOT NULL DEFAULT 'created',
        strategy         TEXT,
        confidence       REAL,
        risk_level       TEXT,
        created_at       TEXT NOT NULL DEFAULT (datetime('now')),
        started_at       TEXT,
        completed_at     TEXT,
        completion_reason TEXT,
        failure_reason   TEXT,
        parent_task_id   TEXT REFERENCES tasks(id),
        checkpoint_json  TEXT
      );

      CREATE TABLE IF NOT EXISTS sessions (
        id          TEXT PRIMARY KEY,
        task_id     TEXT NOT NULL REFERENCES tasks(id),
        parent_session_id TEXT REFERENCES sessions(id),
        agent       TEXT NOT NULL,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE TABLE IF NOT EXISTS agents (
        name         TEXT PRIMARY KEY,
        role         TEXT NOT NULL,
        capabilities TEXT
      );

      CREATE TABLE IF NOT EXISTS events (
        id          TEXT PRIMARY KEY,
        task_id     TEXT NOT NULL REFERENCES tasks(id),
        type        TEXT NOT NULL,
        agent       TEXT,
        payload_json TEXT,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE TABLE IF NOT EXISTS tool_calls (
        id          TEXT PRIMARY KEY,
        task_id     TEXT NOT NULL REFERENCES tasks(id),
        session_id  TEXT,
        agent       TEXT,
        tool_name   TEXT NOT NULL,
        args_json   TEXT,
        result_json TEXT,
        exit_code   INTEGER,
        started_at  TEXT,
        finished_at TEXT,
        error       TEXT
      );

      CREATE TABLE IF NOT EXISTS delegations (
        id            TEXT PRIMARY KEY,
        task_id       TEXT NOT NULL REFERENCES tasks(id),
        parent_agent  TEXT NOT NULL,
        child_agent   TEXT NOT NULL,
        objective     TEXT NOT NULL,
        owned_files   TEXT,
        status        TEXT NOT NULL DEFAULT 'pending',
        created_at    TEXT NOT NULL DEFAULT (datetime('now')),
        completed_at  TEXT,
        result_json   TEXT
      );

      CREATE TABLE IF NOT EXISTS routing_decisions (
        id          TEXT PRIMARY KEY,
        task_id     TEXT NOT NULL REFERENCES tasks(id),
        strategy    TEXT NOT NULL,
        score       REAL,
        confidence  REAL,
        signals_json TEXT,
        fallback    INTEGER DEFAULT 0,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE TABLE IF NOT EXISTS audit_runs (
        id               TEXT PRIMARY KEY,
        task_id          TEXT NOT NULL REFERENCES tasks(id),
        trigger_source   TEXT NOT NULL,
        scope_hash       TEXT NOT NULL,
        auditor_agent    TEXT,
        status           TEXT NOT NULL DEFAULT 'pending',
        created_at       TEXT NOT NULL DEFAULT (datetime('now')),
        completed_at     TEXT,
        finding_json     TEXT,
        UNIQUE(task_id, scope_hash)
      );

      CREATE TABLE IF NOT EXISTS retry_fingerprints (
        id          TEXT PRIMARY KEY,
        task_id     TEXT NOT NULL REFERENCES tasks(id),
        fingerprint TEXT NOT NULL,
        attempt     INTEGER NOT NULL DEFAULT 1,
        strategy    TEXT,
        error_hash  TEXT,
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(task_id, fingerprint)
      );

      CREATE TABLE IF NOT EXISTS verification_runs (
        id            TEXT PRIMARY KEY,
        task_id       TEXT NOT NULL REFERENCES tasks(id),
        category      TEXT NOT NULL,
        command       TEXT,
        exit_code     INTEGER,
        output_digest TEXT,
        status        TEXT NOT NULL DEFAULT 'pending',
        started_at    TEXT,
        finished_at   TEXT,
        error         TEXT
      );

      CREATE TABLE IF NOT EXISTS checkpoints (
        id           TEXT PRIMARY KEY,
        task_id      TEXT NOT NULL REFERENCES tasks(id),
        phase        TEXT NOT NULL,
        state_json   TEXT NOT NULL,
        created_at   TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE TABLE IF NOT EXISTS context_items (
        id           TEXT PRIMARY KEY,
        task_id      TEXT NOT NULL REFERENCES tasks(id),
        file_path    TEXT,
        excerpt_hash TEXT,
        char_count   INTEGER,
        provenance   TEXT,
        included_reason TEXT,
        created_at   TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE TABLE IF NOT EXISTS policy_decisions (
        id            TEXT PRIMARY KEY,
        task_id       TEXT NOT NULL REFERENCES tasks(id),
        agent         TEXT NOT NULL,
        action        TEXT NOT NULL,
        normalized_action TEXT,
        policy_level  INTEGER NOT NULL,
        result        TEXT NOT NULL,
        matching_rule TEXT,
        created_at    TEXT NOT NULL DEFAULT (datetime('now'))
      );

      -- Phase 2 placeholder table (schema only — no enforcement)
      CREATE TABLE IF NOT EXISTS budget_interfaces (
        id            TEXT PRIMARY KEY,
        task_id       TEXT NOT NULL REFERENCES tasks(id),
        phase2_mode   TEXT DEFAULT 'advisory',
        provider_boundary_enforced INTEGER DEFAULT 0,
        hard_limit_available       INTEGER DEFAULT 0,
        created_at    TEXT NOT NULL DEFAULT (datetime('now'))
      );

      CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
      CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id);
      CREATE INDEX IF NOT EXISTS idx_delegations_task ON delegations(task_id);
      CREATE INDEX IF NOT EXISTS idx_audit_runs_task ON audit_runs(task_id);
      CREATE INDEX IF NOT EXISTS idx_retry_task ON retry_fingerprints(task_id);
      CREATE INDEX IF NOT EXISTS idx_tool_calls_task ON tool_calls(task_id);

    COMMIT;`);
  }

  close(): void {
    this.db.close();
  }

  /** Check database integrity */
  checkIntegrity(): string | null {
    try {
      const row = this.db.prepare('PRAGMA integrity_check').get() as { 'integrity_check': string };
      return row['integrity_check'] === 'ok' ? null : row['integrity_check'];
    } catch (e) {
      return String(e);
    }
  }
}
