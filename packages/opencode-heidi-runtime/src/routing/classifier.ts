/**
 * Deterministic routing classifier — weighted signal matching.
 * Direct execution is the default. No mandatory scout/specialist/auditor.
 */

import type { Strategy, RoutingDecision } from '../lifecycle/state-machine.js';
import { extractSignals, type TaskSignals } from './signals.js';

export interface ClassifyInput {
  taskText: string;
  userRequestedAgent?: string;
  fileDiscoveryConfidence?: number;
  taskAmbiguity?: number;
  expectedFileCount?: number;
  hasIndependentParallelWork?: boolean;
  verificationComplexity?: number;
}

interface Candidate {
  strategy: Strategy;
  score: number;
  signals: string[];
}

export function classifyTask(input: ClassifyInput): RoutingDecision {
  const signals = extractSignals(input.taskText, input.userRequestedAgent);

  // Fast path check — if applicable, return immediately without evaluating other strategies
  if (isFastPath(input, signals)) {
    return {
      strategy: 'fast_path',
      score: 0,
      confidence: 0.9,
      signals: ['clear objective', 'small scope', 'low risk', 'documentation change'],
      fallback: false,
    };
  }

  const candidates = evaluateCandidates(signals, input);
  candidates.sort((a, b) => b.score - a.score);

  const best = candidates[0];

  // Compute confidence
  const topScore = best?.score ?? 0;
  const runnerUpScore = candidates[1]?.score ?? 0;
  const spread = topScore - runnerUpScore;
  const confidence = computeConfidence(topScore, spread, input.taskAmbiguity);

  return {
    strategy: best?.strategy ?? 'direct',
    score: topScore,
    confidence,
    signals: best?.signals ?? [],
    uncertainty: confidence < 0.5 ? 'low signal clarity, routing to direct execution' : undefined,
    fallback: best?.strategy === 'direct' && topScore === 0,
  };
}

function isFastPath(input: ClassifyInput, signals: TaskSignals): boolean {
  return (
    (input.taskAmbiguity ?? 1) < 0.3 &&
    (input.expectedFileCount ?? 1) <= 2 &&
    signals.estimatedFileCount <= 1 &&
    !signals.hasSecurityTerms &&
    !signals.hasProductionTerms &&
    !signals.hasAuthTerms &&
    !signals.hasArchitectureTerms &&
    !signals.isMachineLevel &&
    !signals.userRequestedAgent &&
    signals.exactPhrases.length === 0
  );
}

function evaluateCandidates(signals: TaskSignals, input: ClassifyInput): Candidate[] {
  const candidates: Candidate[] = [];
  const s = signals;

  // fast_path: must have ALL conditions
  {
    const isFastPath =
      input.taskAmbiguity !== undefined && input.taskAmbiguity < 0.3 &&
      (input.expectedFileCount ?? 1) <= 2 &&
      !s.hasSecurityTerms &&
      !s.hasProductionTerms &&
      !s.hasAuthTerms &&
      !s.hasArchitectureTerms &&
      !s.isMachineLevel &&
      !s.hasCiTerms &&
      !s.hasBugTerms &&
      !s.userRequestedAgent &&
      s.estimatedFileCount <= 1;

    if (isFastPath) {
      candidates.push({
        strategy: 'fast_path',
        score: 5,
        signals: ['clear objective', 'small scope', 'low risk', 'documentation change'],
      });
    }
  }

  // direct: default strategy
  {
    let score = 10;
    const sigs: string[] = ['direct execution default'];
    if (s.exactPhrases.length === 0 && !s.userRequestedAgent) score += 5;
    if (s.estimatedFileCount <= 2) score += 3;
    if (s.isReversible) score += 2;
    candidates.push({ strategy: 'direct', score, signals: sigs });
  }

  // single_specialist
  {
    let score = 0;
    const sigs: string[] = [];
    if (s.hasFrontend && !s.hasBackend) { score += 12; sigs.push('frontend domain'); }
    if (s.hasBackend && !s.hasFrontend) { score += 12; sigs.push('backend domain'); }
    if (s.hasBugTerms) { score += 8; sigs.push('bug/defect detected'); }
    if (s.hasDatabaseTerms && !s.hasSecurityTerms) { score += 6; sigs.push('database scope'); }
    if (score > 0) candidates.push({ strategy: 'single_specialist', score, signals: sigs });
  }

  // audit_only
  {
    const auditPhrases = ['code review', 'security review', 'audit', 'pr review', 'architecture review'];
    const matched = auditPhrases.filter(p => s.exactPhrases.includes(p) || signals.tokens.includes(p));
    if (matched.length > 0 || s.userRequestedAgent === 'auditor') {
      candidates.push({
        strategy: 'audit_only',
        score: 20 + matched.length * 5,
        signals: [...matched, ...(s.userRequestedAgent === 'auditor' ? ['user-requested auditor'] : [])],
      });
    } else if (s.hasSecurityTerms && s.hasAuthTerms) {
      candidates.push({
        strategy: 'audit_only',
        score: 15,
        signals: ['security-sensitive code path'],
      });
    }
  }

  // debug_investigation
  {
    // CI issue: only when combined with failure indicators
    const isCiFailure = s.hasCiTerms && (s.exactPhrases.includes('pipeline failure') || s.tokens.includes('failure') || s.tokens.includes('failing') || s.tokens.includes('broken'));
    if (isCiFailure || s.hasBugTerms) {
      let score = 12;
      const sigs: string[] = [];
      if (isCiFailure) { score += 10; sigs.push('ci/pipeline failure'); }
      if (s.hasBugTerms) { score += 8; sigs.push('bug/defect'); }
      if (s.isMachineLevel) score -= 3;
      candidates.push({ strategy: 'debug_investigation', score, signals: sigs });
    }
  }

  // planning_only
  {
    if (s.hasArchitectureTerms) {
      candidates.push({
        strategy: 'planning_only',
        score: 18,
        signals: ['architecture/planning scope'],
      });
    }
  }

  // parallel_specialists
  {
    if (s.hasFrontend && s.hasBackend && input.hasIndependentParallelWork) {
      candidates.push({
        strategy: 'parallel_specialists',
        score: 20,
        signals: ['both frontend and backend domains', 'independent parallel work'],
      });
    }
  }

  // blocked_for_user_action
  {
    if (s.isMachineLevel) {
      candidates.push({
        strategy: 'blocked_for_user_action',
        score: 25,
        signals: ['machine-level operation requires user action'],
      });
    }
  }

  return candidates;
}

function computeConfidence(topScore: number, spread: number, ambiguity?: number): number {
  const base = Math.min(1.0, topScore / 30);
  const spreadFactor = Math.min(1.0, spread / 10);
  const ambiguityPenalty = (ambiguity ?? 0) * 0.5;
  return Math.max(0, Math.min(1, (base * 0.4 + spreadFactor * 0.4 + 0.2) - ambiguityPenalty));
}
