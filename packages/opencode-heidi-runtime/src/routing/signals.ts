/**
 * Normalized signal extraction for routing classification.
 * Uses word-boundary token matching, not substring matching.
 */

export interface TaskSignals {
  tokens: string[];
  exactPhrases: string[];
  hasFrontend: boolean;
  hasBackend: boolean;
  hasSecurityTerms: boolean;
  hasProductionTerms: boolean;
  hasDatabaseTerms: boolean;
  hasAuthTerms: boolean;
  hasTestTerms: boolean;
  hasArchitectureTerms: boolean;
  hasCiTerms: boolean;
  hasBugTerms: boolean;
  hasDocTerms: boolean;
  userRequestedAgent?: string;
  estimatedFileCount: number;
  isMachineLevel: boolean;
  isReversible: boolean;
}

const FRONTEND_WORDS = new Set(['frontend', 'ui', 'component', 'react', 'tailwind', 'css', 'layout', 'page', 'form', 'button', 'style', 'styling']);
const BACKEND_WORDS = new Set(['backend', 'api', 'database', 'prisma', 'migration', 'server', 'endpoint', 'route', 'controller']);
const SECURITY_WORDS = new Set(['auth', 'authenticate', 'authorize', 'permission', 'oauth', 'jwt', 'token', 'session', 'encrypt', 'decrypt', 'hash', 'salt']);
const PRODUCTION_WORDS = new Set(['deploy', 'production', 'release', 'rollback', 'canary', 'blue-green']);
const DATABASE_WORDS = new Set(['database', 'prisma', 'migration', 'schema', 'sql', 'query', 'table', 'index', 'model']);
const AUTH_WORDS = new Set(['auth', 'login', 'logout', 'signup', 'register', 'password', 'oauth', 'jwt', 'session']);
const TEST_WORDS = new Set(['test', 'spec', 'assert', 'mock', 'stub', 'fixture', 'coverage']);
const ARCHITECTURE_WORDS = new Set(['architecture', 'design', 'roadmap', 'plan', 'spec', 'proposal']);
const CI_WORDS = new Set(['ci', 'pipeline', 'github action', 'workflow', 'build', 'failing']);
const BUG_WORDS = new Set(['bug', 'crash', 'broken', 'bugfix', 'regression']);
const DOC_WORDS = new Set(['typo', 'spelling', 'comment', 'docs', 'documentation', 'readme', 'wording']);

const MACHINE_LEVEL_PHRASES = ['reboot', 'restart', 'shutdown', 'sudo', 'kernel', 'bios', 'driver', 'hardware'];
const REVERSIBLE_PHRASES = ['npm install', 'pip install', 'bundle install', 'git checkout', 'git revert', 'git commit', 'branch'];

function tokenize(text: string): string[] {
  return text.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
}

function extractExactPhrases(text: string): string[] {
  const phrases: string[] = [];
  const patterns = [
    /\bc(?:ode|i)\s+review\b/gi,
    /\bsecurity\s+review\b/gi,
    /\bcode\s+audit\b/gi,
    /\bschema\s+migration\b/gi,
    /\bpipeline\s+failure\b/gi,
    /\bbroken\s+build\b/gi,
    /\bfailing\s+test\b/gi,
    /\bproduction\s+bug\b/gi,
    /\barchitecture\s+plan\b/gi,
    /\bfrontend\s+and\s+backend\b/gi,
    /\bfull\s+stack\b/gi,
  ];
  for (const p of patterns) {
    const m = text.match(p);
    if (m) phrases.push(m[0].toLowerCase());
  }
  return phrases;
}

export function extractSignals(taskText: string, userRequestedAgent?: string): TaskSignals {
  const lower = taskText.toLowerCase();
  const tokens = tokenize(lower);
  const tokenSet = new Set(tokens);
  const exactPhrases = extractExactPhrases(lower);

  return {
    tokens,
    exactPhrases,
    hasFrontend: [...FRONTEND_WORDS].some(w => tokenSet.has(w)),
    hasBackend: [...BACKEND_WORDS].some(w => tokenSet.has(w)),
    hasSecurityTerms: [...SECURITY_WORDS].some(w => tokenSet.has(w)),
    hasProductionTerms: [...PRODUCTION_WORDS].some(w => tokenSet.has(w)),
    hasDatabaseTerms: [...DATABASE_WORDS].some(w => tokenSet.has(w)),
    hasAuthTerms: [...AUTH_WORDS].some(w => tokenSet.has(w)),
    hasTestTerms: [...TEST_WORDS].some(w => tokenSet.has(w)),
    hasArchitectureTerms: [...ARCHITECTURE_WORDS].some(w => tokenSet.has(w)),
    hasCiTerms: [...CI_WORDS].some(w => tokenSet.has(w)),
    hasBugTerms: [...BUG_WORDS].some(w => tokenSet.has(w)),
    hasDocTerms: [...DOC_WORDS].some(w => tokenSet.has(w)),
    userRequestedAgent,
    estimatedFileCount: estimateFiles(lower, tokens),
    isMachineLevel: MACHINE_LEVEL_PHRASES.some(p => lower.includes(p)),
    isReversible: REVERSIBLE_PHRASES.some(p => lower.includes(p)),
  };
}

function estimateFiles(text: string, tokens: string[]): number {
  if (/\b(add|create|new)\b/.test(text) && (tokens.includes('page') || tokens.includes('endpoint') || tokens.includes('route'))) {
    return 3;
  }
  if (/\b(typo|spelling|comment)\b/.test(text)) return 1;
  if (/\b(migration|refactor|restructur)\b/.test(text)) return 5;
  return 2;
}
