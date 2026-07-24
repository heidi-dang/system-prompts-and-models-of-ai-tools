/**
 * Policy engine — evaluates tool usage and permissions.
 * Fail closed for protected actions.
 */

export interface PolicyDecision {
  result: 'allow' | 'deny' | 'approval_required';
  policyLevel: 0 | 1 | 2 | 3;
  matchingRule: string;
  message?: string;
}

// Tools that are always allowed (level 0)
const READ_ONLY_TOOLS = new Set(['read', 'glob', 'grep', 'search', 'file_search']);

// File write tools that require policy evaluation
const WRITE_TOOLS = new Set(['edit', 'write', 'create_file']);

// Dangerous tools (level 3)
const DANGEROUS_TOOLS = new Set(['delete_file', 'rm', 'rmdir', 'sudo']);

export class PolicyEngine {
  evaluateTool(toolName: string, args: unknown, taskId: string): PolicyDecision {
    // Read-only tools — always allow
    if (READ_ONLY_TOOLS.has(toolName)) {
      return { result: 'allow', policyLevel: 0, matchingRule: 'read-only tool' };
    }

    // Dangerous tools — deny
    if (DANGEROUS_TOOLS.has(toolName)) {
      return {
        result: 'deny',
        policyLevel: 3,
        matchingRule: 'dangerous tool blocked: requires user action',
        message: 'This operation requires explicit user approval. Report the exact command to the user.',
      };
    }

    // Write tools — check scope
    if (WRITE_TOOLS.has(toolName)) {
      return this.evaluateWriteOperation(toolName, args);
    }

    // Default — allow (bash, task, etc.)
    return { result: 'allow', policyLevel: 1, matchingRule: 'default tool allow' };
  }

  private evaluateWriteOperation(tool: string, args: unknown): PolicyDecision {
    const path = extractPath(args);
    if (!path) return { result: 'allow', policyLevel: 1, matchingRule: 'write tool, no path identified' };

    // Block path traversal
    if (path.includes('..') || path.includes('~') && !path.startsWith('~/.config/opencode')) {
      return { result: 'deny', policyLevel: 2, matchingRule: 'path traversal detected' };
    }

    // Allow repository-scoped writes
    return { result: 'allow', policyLevel: 1, matchingRule: 'repository-scoped write' };
  }
}

function extractPath(args: unknown): string | null {
  if (typeof args === 'object' && args !== null) {
    const a = args as Record<string, unknown>;
    return (typeof a.filePath === 'string' ? a.filePath :
            typeof a.path === 'string' ? a.path :
            typeof a.file === 'string' ? a.file : null);
  }
  return null;
}
