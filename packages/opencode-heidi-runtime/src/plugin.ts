/**
 * OpenCode plugin entry point for Heidi Runtime.
 * Registers lifecycle hooks, custom tools, and governance middleware.
 */

import type { Plugin, Hooks } from '@opencode-ai/plugin';
import type { ToolDefinition } from '@opencode-ai/plugin/tool';
import { RuntimeDatabase } from './storage/database.js';
import { TaskManager } from './lifecycle/task-manager.js';
import { SessionMapper } from './lifecycle/session-mapper.js';
import { classifyTask } from './routing/classifier.js';
import { PolicyEngine } from './governance/policy-engine.js';
import { CommandPolicy } from './governance/command-policy.js';
import { RetryController } from './retries/retry-controller.js';
import { AuditController } from './audits/audit-controller.js';
import { VerificationEngine } from './verification/executor.js';
import { loadConfig, resolveDbPath } from './config/loader.js';
import type { HeidiRuntimeConfig } from './config/schema.js';

export const heidiRuntimePlugin: Plugin = async (input, options?: Record<string, unknown>) => {
  const config = loadConfig();
  const dbPath = resolveDbPath(config.dbPath);
  const db = new RuntimeDatabase(dbPath);
  const taskManager = new TaskManager(db);
  const sessionMapper = new SessionMapper(db, taskManager);
  const policyEngine = new PolicyEngine();
  const commandPolicy = new CommandPolicy();
  const retryController = new RetryController(db);
  const auditController = new AuditController(db);
  const verificationEngine = new VerificationEngine();

  // Track current task
  let currentTaskId: string | null = null;

  const hooks: Hooks = {
    /** Track lifecycle events */
    event: async ({ event }) => {
      const evt = event as unknown as { type?: string; agent?: string };
      if (currentTaskId) {
        taskManager.recordEvent(currentTaskId, evt.type ?? 'unknown', evt.agent);
      }
    },

    /** Handle new chat messages to detect task start */
    'chat.message': async (input) => {
      const task = sessionMapper.mapMessageToTask(input);
      currentTaskId = task.id;
      const routing = classifyTask({
        taskText: task.objective,
        fileDiscoveryConfidence: 0.8,
        taskAmbiguity: 0.1,
        expectedFileCount: 2,
      });
      taskManager.recordRouting(task.id, routing);
      taskManager.transitionTask(task.id, 'classified');
    },

    /** Governance: command execution policy */
    'command.execute.before': async (input, output) => {
      if (!currentTaskId) return;
      const ci = input as unknown as { command: string; sessionID: string; arguments: string };
      const decision = commandPolicy.evaluate(ci.command, currentTaskId, 'heidi');
      db.connection.prepare(`
        INSERT INTO policy_decisions (id, task_id, agent, action, normalized_action, policy_level, result, matching_rule)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `).run(
        `pd_${Date.now()}`,
        currentTaskId,
        'heidi',
        ci.command,
        commandPolicy.normalize(ci.command),
        decision.policyLevel,
        decision.result,
        decision.matchingRule
      );
      if (decision.result === 'deny') {
        const o = output as unknown as { parts: { type: string; text: string }[] };
        o.parts = [{ type: 'text', text: `[runtime] command denied: ${decision.matchingRule}. ${decision.message ?? ''}` }];
      }
    },

    /** Governance: tool execution policy */
    'tool.execute.before': async (input, output) => {
      if (!currentTaskId) return;
      const ti = input as unknown as { tool: string; sessionID: string; callID: string; args?: unknown };
      const decision = policyEngine.evaluateTool(ti.tool, ti.args, currentTaskId);
      if (decision.result === 'deny') {
        const o = output as unknown as { args: Record<string, unknown> };
        o.args = { ...(o.args ?? {}), _denied: true, _reason: decision.matchingRule };
      }
    },

    /** Track tool results */
    'tool.execute.after': async (input) => {
      if (!currentTaskId) return;
      db.connection.prepare(`
        INSERT INTO tool_calls (id, task_id, tool_name, args_json, result_json, exit_code, finished_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
      `).run(
        `tc_${Date.now()}`,
        currentTaskId,
        input.tool,
        JSON.stringify(input.args ?? {}),
        null,
        null
      );
    },

    /** Register custom tools */
    tool: {
      heidi_task_status: {
        description: 'Get the current task status, routing decision, and completion readiness',
        parameters: {
          type: 'object',
          properties: {
            taskId: { type: 'string', description: 'Optional task ID. Defaults to current task.' },
          },
        },
        execute: async (args: { taskId?: string }) => {
          const id = args.taskId ?? currentTaskId;
          if (!id) return JSON.stringify({ error: 'no active task' });
          const task = taskManager.getTask(id);
          if (!task) return JSON.stringify({ error: 'task not found' });
          const ready = taskManager.isReadyToComplete(id);
          return JSON.stringify({ task, readyToComplete: ready.ready, blockReason: ready.reason });
        },
      } as unknown as ToolDefinition,

      heidi_delegate: {
        description: 'Delegate work to a specialist agent with controlled ownership',
        parameters: {
          type: 'object',
          properties: {
            agent: { type: 'string', description: 'Agent name (frontend, backend, debugger, auditor, planner)' },
            objective: { type: 'string', description: 'Task objective for the specialist' },
            ownedFiles: { type: 'array', items: { type: 'string' }, description: 'Files the specialist owns' },
            verificationRequired: { type: 'boolean', description: 'Require verification after completion' },
          },
          required: ['agent', 'objective'],
        },
        execute: async (args: { agent: string; objective: string; ownedFiles?: string[]; verificationRequired?: boolean }) => {
          if (!currentTaskId) return JSON.stringify({ error: 'no active task' });
          // Check delegation limit
          const existingDelegations = db.connection.prepare(
            `SELECT COUNT(*) as count FROM delegations WHERE task_id = ?`
          ).get(currentTaskId) as { count: number };
          if (existingDelegations.count >= 2) {
            return JSON.stringify({ error: 'max delegations reached (2)' });
          }
          // Create delegation record
          db.connection.prepare(`
            INSERT INTO delegations (id, task_id, parent_agent, child_agent, objective, owned_files, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
          `).run(`del_${Date.now()}`, currentTaskId, 'heidi', args.agent, args.objective,
            JSON.stringify(args.ownedFiles ?? []));
          return JSON.stringify({ ok: true, agent: args.agent, objective: args.objective });
        },
      } as unknown as ToolDefinition,

      heidi_verify: {
        description: 'Execute a verification command and record the result',
        parameters: {
          type: 'object',
          properties: {
            command: { type: 'string', description: 'Verification command to run' },
            category: { type: 'string', description: 'Verification category (lint, typecheck, test, build)' },
            workingDirectory: { type: 'string', description: 'Working directory' },
          },
          required: ['command', 'category'],
        },
        execute: async (args: { command: string; category: string; workingDirectory?: string }) => {
          if (!currentTaskId) return JSON.stringify({ error: 'no active task' });
          const result = await verificationEngine.run(args.command, args.category, args.workingDirectory);
          db.connection.prepare(`
            INSERT INTO verification_runs (id, task_id, category, command, exit_code, output_digest, status, finished_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
          `).run(`vr_${Date.now()}`, currentTaskId, args.category, args.command, result.exitCode,
            result.outputDigest, result.exitCode === 0 ? 'pass' : 'fail');
          return JSON.stringify(result);
        },
      } as unknown as ToolDefinition,

      heidi_finish: {
        description: 'Mark the current task as complete or partially complete',
        parameters: {
          type: 'object',
          properties: {
            status: { type: 'string', enum: ['completed', 'partially_completed', 'failed'], description: 'Final status' },
            reason: { type: 'string', description: 'Completion reason or failure reason' },
          },
          required: ['status'],
        },
        execute: async (args: { status: string; reason?: string }) => {
          if (!currentTaskId) return JSON.stringify({ error: 'no active task' });
          const validStatuses = ['completed', 'partially_completed', 'failed'];
          if (!validStatuses.includes(args.status)) {
            return JSON.stringify({ error: `invalid status: ${args.status}` });
          }
          taskManager.transitionTask(currentTaskId, args.status as any, args.reason);
          taskManager.recordEvent(currentTaskId, 'task_completed', 'heidi', { status: args.status, reason: args.reason });
          currentTaskId = null;
          return JSON.stringify({ ok: true, status: args.status });
        },
      } as unknown as ToolDefinition,
    },

    /** Cleanup on plugin dispose */
    dispose: async () => {
      db.close();
    },
  };

  return hooks;
};
