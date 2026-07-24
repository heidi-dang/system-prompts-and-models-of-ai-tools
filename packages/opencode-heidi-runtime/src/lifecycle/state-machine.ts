/**
 * Task state machine — validated lifecycle transitions.
 */

export type TaskStatus =
  | 'created'
  | 'classified'
  | 'context_ready'
  | 'executing'
  | 'verifying'
  | 'completed'
  | 'blocked'
  | 'failed'
  | 'cancelled'
  | 'budget_exhausted'
  | 'waiting_for_user'
  | 'partially_completed';

export interface TaskRecord {
  id: string;
  sessionId?: string;
  objective: string;
  status: TaskStatus;
  strategy?: string;
  confidence?: number;
  riskLevel?: string;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  completionReason?: string;
  failureReason?: string;
  parentTaskId?: string;
  checkpointJson?: string;
}

export type Strategy =
  | 'fast_path'
  | 'direct'
  | 'single_specialist'
  | 'parallel_specialists'
  | 'audit_only'
  | 'debug_investigation'
  | 'planning_only'
  | 'blocked_for_user_action';

export interface RoutingDecision {
  strategy: Strategy;
  score: number;
  confidence: number;
  signals: string[];
  uncertainty?: string;
  fallback: boolean;
}

export interface DelegationContract {
  parentTaskId: string;
  childId: string;
  agentRole: string;
  objective: string;
  successCriteria: string[];
  ownedFiles: string[];
  readablePaths: string[];
  prohibitedPaths: string[];
  allowedTools: string[];
  contextPack: string;
  verificationRequired: boolean;
  timeoutMs: number;
  maxRetries: number;
}

export interface OwnershipBoundary {
  agent: string;
  ownedFiles: string[];
  readablePaths: string[];
  prohibitedPaths: string[];
  lockedPaths: string[];
}

export interface PolicyDecision {
  action: string;
  normalizedAction: string;
  policyLevel: 0 | 1 | 2 | 3;
  result: 'allow' | 'deny' | 'approval_required';
  matchingRule: string;
  taskId: string;
  agent: string;
  timestamp: string;
}

export interface VerificationRecord {
  command: string;
  workingDirectory: string;
  startTime: string;
  finishTime: string;
  exitCode: number;
  outputDigest: string;
  status: 'pass' | 'fail' | 'skipped';
  skipReason?: string;
  relatedFiles: string[];
}

export interface AuditRecord {
  id: string;
  taskId: string;
  triggerSource: string;
  scopeHash: string;
  status: 'pending' | 'running' | 'completed' | 'deduplicated';
  completedAt?: string;
  findingSummary?: string;
}

export interface RetryFingerprint {
  taskObjective: string;
  strategy: string;
  agent: string;
  toolOrCommand: string;
  files: string[];
  normalizedError: string;
  contextHash: string;
  environmentSignature: string;
}

// Valid state transitions
const TRANSITIONS: Record<TaskStatus, TaskStatus[]> = {
  created: ['classified', 'blocked', 'cancelled'],
  classified: ['context_ready', 'blocked', 'cancelled'],
  context_ready: ['executing', 'blocked', 'cancelled'],
  executing: ['verifying', 'blocked', 'failed', 'cancelled', 'budget_exhausted', 'waiting_for_user'],
  verifying: ['completed', 'executing', 'blocked', 'failed', 'partially_completed'],
  completed: [],
  blocked: ['classified', 'executing', 'cancelled'],
  failed: [],
  cancelled: [],
  budget_exhausted: ['completed', 'blocked'],
  waiting_for_user: ['executing', 'blocked', 'cancelled'],
  partially_completed: ['blocked'],
};

export function isValidTransition(from: TaskStatus, to: TaskStatus): boolean {
  return TRANSITIONS[from]?.includes(to) ?? false;
}

export function validateTransition(from: TaskStatus, to: TaskStatus): void {
  if (!isValidTransition(from, to)) {
    throw new Error(`Invalid state transition: ${from} → ${to}`);
  }
}
