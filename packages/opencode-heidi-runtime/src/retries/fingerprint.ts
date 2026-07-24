/**
 * Normalized retry fingerprint — identifies equivalent failures.
 */
import { createHash } from 'crypto';
import type { RetryFingerprint } from '../lifecycle/state-machine.js';

export function hashFingerprint(fp: RetryFingerprint): string {
  const canonical = JSON.stringify({
    objective: normalizeText(fp.taskObjective),
    strategy: fp.strategy,
    agent: fp.agent,
    tool: fp.toolOrCommand,
    files: [...fp.files].sort(),
    error: normalizeError(fp.normalizedError),
    context: fp.contextHash,
    env: fp.environmentSignature,
  });
  return createHash('sha256').update(canonical).digest('hex').slice(0, 16);
}

export function fingerprintChanged(a: RetryFingerprint, b: RetryFingerprint): boolean {
  const keys: (keyof RetryFingerprint)[] = ['strategy', 'toolOrCommand', 'files'];
  for (const k of keys) {
    const av = a[k];
    const bv = b[k];
    if (Array.isArray(av) && Array.isArray(bv)) {
      if (JSON.stringify([...av].sort()) !== JSON.stringify([...bv].sort())) return true;
    } else if (av !== bv) {
      return true;
    }
  }
  return false;
}

function normalizeText(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

function normalizeError(error: string): string {
  // Extract error type (first line or error class name)
  const firstLine = error.split('\n')[0].trim();
  const classMatch = firstLine.match(/(\w+Error|\w+Exception)/);
  return classMatch?.[1] ?? firstLine.slice(0, 80);
}
