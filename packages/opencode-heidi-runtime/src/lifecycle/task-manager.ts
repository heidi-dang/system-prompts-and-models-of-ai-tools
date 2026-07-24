import { randomUUID } from 'crypto';
import { RuntimeDatabase } from '../storage/database.js';
import { type TaskRecord, type TaskStatus, validateTransition, isValidTransition } from './state-machine.js';
import type { Strategy, RoutingDecision } from './state-machine.js';

export class TaskManager {
  constructor(private db: RuntimeDatabase) {}

  /** Create a new task from a user objective */
  createTask(objective: string, sessionId?: string, parentTaskId?: string): TaskRecord {
    const id = `task_${Date.now()}_${randomUUID().slice(0, 8)}`;
    const now = new Date().toISOString();
    const task: TaskRecord = {
      id,
      sessionId,
      objective,
      status: 'created',
      createdAt: now,
      parentTaskId,
    };

    this.db.connection.prepare(`
      INSERT INTO tasks (id, session_id, objective, status, created_at, parent_task_id)
      VALUES (?, ?, ?, 'created', ?, ?)
    `).run(id, sessionId ?? null, objective, now, parentTaskId ?? null);

    return task;
  }

  /** Get task by ID */
  getTask(taskId: string): TaskRecord | null {
    const row = this.db.connection.prepare(`
      SELECT id, session_id as sessionId, objective, status, strategy, confidence,
             risk_level as riskLevel, created_at as createdAt, started_at as startedAt,
             completed_at as completedAt, completion_reason as completionReason,
             failure_reason as failureReason, parent_task_id as parentTaskId
      FROM tasks WHERE id = ?
    `).get(taskId) as TaskRecord | undefined;
    return row ?? null;
  }

  /** Transition task to a new state */
  transitionTask(taskId: string, newStatus: TaskStatus, reason?: string): TaskRecord {
    const task = this.getTask(taskId);
    if (!task) throw new Error(`Task not found: ${taskId}`);
    validateTransition(task.status, newStatus);

    const now = new Date().toISOString();
    const updates: string[] = ['status = ?'];
    const params: any[] = [newStatus];

    if (newStatus === 'executing' && !task.startedAt) {
      updates.push('started_at = ?');
      params.push(now);
    }
    if (['completed', 'failed', 'cancelled', 'budget_exhausted', 'partially_completed'].includes(newStatus)) {
      updates.push('completed_at = ?');
      params.push(now);
    }
    if (newStatus === 'failed' && reason) {
      updates.push('failure_reason = ?');
      params.push(reason);
    }
    if (['completed', 'partially_completed'].includes(newStatus)) {
      updates.push('completion_reason = ?');
      params.push(reason ?? null);
    }

    params.push(taskId);
    this.db.connection.prepare(`UPDATE tasks SET ${updates.join(', ')} WHERE id = ?`).run(...params);
    return this.getTask(taskId)!;
  }

  /** Record routing decision */
  recordRouting(taskId: string, routing: RoutingDecision): void {
    this.db.connection.prepare(`
      INSERT INTO routing_decisions (id, task_id, strategy, score, confidence, signals_json, fallback)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(
      `r_${randomUUID().slice(0, 8)}`,
      taskId,
      routing.strategy,
      routing.score,
      routing.confidence,
      JSON.stringify(routing.signals),
      routing.fallback ? 1 : 0
    );

    this.db.connection.prepare(`
      UPDATE tasks SET strategy = ?, confidence = ? WHERE id = ?
    `).run(routing.strategy, routing.confidence, taskId);
  }

  /** Record an event */
  recordEvent(taskId: string, type: string, agent?: string, payload?: unknown): void {
    this.db.connection.prepare(`
      INSERT INTO events (id, task_id, type, agent, payload_json)
      VALUES (?, ?, ?, ?, ?)
    `).run(
      `evt_${randomUUID().slice(0, 8)}`,
      taskId,
      type,
      agent ?? null,
      payload ? JSON.stringify(payload) : null
    );
  }

  /** Export task as JSON */
  exportTask(taskId: string): object | null {
    const task = this.getTask(taskId);
    if (!task) return null;

    const events = this.db.connection.prepare(
      `SELECT * FROM events WHERE task_id = ? ORDER BY created_at`
    ).all(taskId);

    const delegations = this.db.connection.prepare(
      `SELECT * FROM delegations WHERE task_id = ? ORDER BY created_at`
    ).all(taskId);

    const audits = this.db.connection.prepare(
      `SELECT * FROM audit_runs WHERE task_id = ? ORDER BY created_at`
    ).all(taskId);

    const verifications = this.db.connection.prepare(
      `SELECT * FROM verification_runs WHERE task_id = ? ORDER BY created_at`
    ).all(taskId);

    const routing = this.db.connection.prepare(
      `SELECT * FROM routing_decisions WHERE task_id = ? ORDER BY created_at`
    ).all(taskId);

    return { task, events, delegations, audits, verifications, routing };
  }

  /** Check task completion readiness */
  isReadyToComplete(taskId: string): { ready: boolean; reason?: string } {
    const task = this.getTask(taskId);
    if (!task) return { ready: false, reason: 'task not found' };
    if (task.status !== 'verifying') return { ready: false, reason: `task is in state ${task.status}` };

    const failedVerifications = this.db.connection.prepare(
      `SELECT COUNT(*) as count FROM verification_runs WHERE task_id = ? AND status = 'fail'`
    ).get(taskId) as { count: number };

    if (failedVerifications.count > 0) {
      return { ready: false, reason: `${failedVerifications.count} verification(s) failed` };
    }

    return { ready: true };
  }

  /** Save checkpoint */
  saveCheckpoint(taskId: string, phase: string): void {
    const task = this.getTask(taskId);
    if (!task) return;
    this.db.connection.prepare(`
      INSERT INTO checkpoints (id, task_id, phase, state_json)
      VALUES (?, ?, ?, ?)
    `).run(`cp_${randomUUID().slice(0, 8)}`, taskId, phase, JSON.stringify(task));
  }

  /** Recover last checkpoint */
  recoverCheckpoint(taskId: string): TaskRecord | null {
    const row = this.db.connection.prepare(`
      SELECT state_json FROM checkpoints WHERE task_id = ? ORDER BY created_at DESC LIMIT 1
    `).get(taskId) as { state_json: string } | undefined;
    if (!row) return null;
    return JSON.parse(row.state_json) as TaskRecord;
  }
}
