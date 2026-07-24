/**
 * Command policy — evaluates shell commands against governance levels.
 */

import type { PolicyDecision } from './policy-engine.js';

// Patterns that indicate machine-level operations (level 3)
const DANGEROUS_PATTERNS = [
  { pattern: /\bsudo\b/, rule: 'sudo command' },
  { pattern: /\breboot\b/, rule: 'reboot' },
  { pattern: /\bshutdown\b/, rule: 'shutdown' },
  { pattern: /\blogout\b/, rule: 'logout' },
  { pattern: /\brm\s+-rf\s+\/$/, rule: 'destructive root delete' },
  { pattern: /\bdd\b/, rule: 'dd disk operation' },
  { pattern: /\bmkfs\b/, rule: 'filesystem creation' },
  { pattern: /\bfdisk\b/, rule: 'disk partitioning' },
  { pattern: /\bpasswd\b/, rule: 'password change' },
  { pattern: /\bchmod\s+777\b/, rule: 'dangerous permissions' },
];

// Patterns that require approval (level 2)
const APPROVAL_PATTERNS = [
  { pattern: /\bgit\s+push\b/, rule: 'git push' },
  { pattern: /\bgit\s+merge\b/, rule: 'git merge' },
  { pattern: /\bgh\s+pr\s+merge\b/, rule: 'PR merge' },
  { pattern: /\bdocker\s+push\b/, rule: 'docker push' },
  { pattern: /\bdeploy\b/, rule: 'deployment' },
  { pattern: /\bnpm\s+publish\b/, rule: 'npm publish' },
  { pattern: /\baws\s+\w+\s+update\b/, rule: 'aws update' },
];

// Patterns that are reversible repository-scoped (level 1)
const REVERSIBLE_PATTERNS = [
  { pattern: /\bnpm\s+install\b/, rule: 'npm install' },
  { pattern: /\bpip\s+install\b/, rule: 'pip install' },
  { pattern: /\bbundle\s+install\b/, rule: 'bundle install' },
  { pattern: /\bgit\s+checkout\s+-?[bB]\b/, rule: 'git branch/checkout' },
  { pattern: /\bgit\s+add\b/, rule: 'git add' },
  { pattern: /\bgit\s+commit\b/, rule: 'git commit' },
  { pattern: /\bnpm\s+run\b/, rule: 'npm run script' },
  { pattern: /\bnpx\b/, rule: 'npx command' },
  { pattern: /\bmake\b/, rule: 'make' },
  { pattern: /\bcargo\b/, rule: 'cargo command' },
  { pattern: /\bpython3?\s+-m\s+(pip|venv|pytest|unittest)\b/, rule: 'python module' },
];

export class CommandPolicy {
  normalize(command: string): string {
    // Strip arguments for normalization
    return command.split(/\s+/).slice(0, 2).join(' ');
  }

  evaluate(command: string, taskId: string, agent: string): PolicyDecision {
    const lower = command.toLowerCase();

    // Check dangerous patterns first (level 3)
    for (const { pattern, rule } of DANGEROUS_PATTERNS) {
      if (pattern.test(lower)) {
        return {
          result: 'deny',
          policyLevel: 3,
          matchingRule: rule,
          message: 'This command requires explicit user approval. Report what you were trying to do.',
        };
      }
    }

    // Check approval patterns (level 2)
    for (const { pattern, rule } of APPROVAL_PATTERNS) {
      if (pattern.test(lower)) {
        return {
          result: 'approval_required',
          policyLevel: 2,
          matchingRule: rule,
          message: `'${rule}' requires user confirmation.`,
        };
      }
    }

    // Check reversible patterns (level 1 — allow by default)
    for (const { pattern, rule } of REVERSIBLE_PATTERNS) {
      if (pattern.test(lower)) {
        return { result: 'allow', policyLevel: 1, matchingRule: rule };
      }
    }

    // Default: allow (reversible, project-scoped)
    return { result: 'allow', policyLevel: 1, matchingRule: 'default allow' };
  }
}
