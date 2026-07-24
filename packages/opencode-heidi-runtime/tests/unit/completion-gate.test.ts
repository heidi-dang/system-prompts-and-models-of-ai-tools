import { describe, it, expect } from 'vitest';
import { CompletionGate } from '../../src/verification/completion-gate.js';

describe('CompletionGate', () => {
  const gate = new CompletionGate();

  it('fast path requires less verification', () => {
    const r = gate.check(
      { status: 'verifying', strategy: 'fast_path' },
      [{ status: 'pass', category: 'lint' }]
    );
    expect(r.hasRequiredChanges).toBe(true);
    expect(r.requiredVerificationRan).toBe(true);
    expect(r.mandatoryVerificationPassed).toBe(true);
    expect(r.confidence).toBeGreaterThan(0.9);
  });

  it('fails when mandatory verification fails', () => {
    const r = gate.check(
      { status: 'verifying', strategy: 'direct' },
      [
        { status: 'pass', category: 'lint' },
        { status: 'fail', category: 'typecheck' },
      ]
    );
    expect(r.mandatoryVerificationPassed).toBe(false);
    expect(r.confidence).toBeLessThan(0.5);
  });

  it('reports low confidence without changes', () => {
    const r = gate.check(
      { status: 'created', strategy: 'direct' },
      []
    );
    expect(r.confidence).toBe(0);
  });

  it('audit-only has no mandatory verification', () => {
    const r = gate.check(
      { status: 'verifying', strategy: 'audit_only' },
      []
    );
    expect(r.requiredVerificationRan).toBe(true); // No categories required
    expect(r.mandatoryVerificationPassed).toBe(true);
  });

  it('debug_investigation requires tests', () => {
    const r = gate.check(
      { status: 'verifying', strategy: 'debug_investigation' },
      [{ status: 'pass', category: 'test' }]
    );
    expect(r.requiredVerificationRan).toBe(true);
  });
});
