/**
 * Session mapper — maps OpenCode sessions to tasks.
 */

import { RuntimeDatabase } from '../storage/database.js';
import { TaskManager } from './task-manager.js';

export class SessionMapper {
  constructor(
    private db: RuntimeDatabase,
    private taskManager: TaskManager,
  ) {}

  /** Map an OpenCode message event to a task */
  mapMessageToTask(input: { sessionID: string; agent?: string; messageID?: string }): { id: string; objective: string } {
    // Check for existing task for this session
    const existing = this.db.connection.prepare(`
      SELECT t.id, t.objective FROM tasks t
      JOIN sessions s ON s.task_id = t.id
      WHERE s.id = ? ORDER BY t.created_at DESC LIMIT 1
    `).get(input.sessionID) as { id: string; objective: string } | undefined;

    if (existing) return existing;

    // Create new task for this session
    const objective = `task_${Date.now()}`;  // Will be refined by context
    const task = this.taskManager.createTask(objective, input.sessionID);

    // Record session
    this.db.connection.prepare(`
      INSERT INTO sessions (id, task_id, agent)
      VALUES (?, ?, ?)
    `).run(input.sessionID, task.id, input.agent ?? 'heidi');

    return { id: task.id, objective };
  }
}
