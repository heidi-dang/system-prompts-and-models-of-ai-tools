import { describe, it, expect } from 'vitest';
import { isValidTransition, validateTransition } from '../../src/lifecycle/state-machine.js';

describe('State machine transitions', () => {
  it('allows created → classified', () => {
    expect(isValidTransition('created', 'classified')).toBe(true);
  });

  it('allows executing → verifying', () => {
    expect(isValidTransition('executing', 'verifying')).toBe(true);
  });

  it('allows verifying → completed', () => {
    expect(isValidTransition('verifying', 'completed')).toBe(true);
  });

  it('blocks completed → executing', () => {
    expect(isValidTransition('completed', 'executing')).toBe(false);
  });

  it('blocks created → completed', () => {
    expect(isValidTransition('created', 'completed')).toBe(false);
  });

  it('allows executing → failed', () => {
    expect(isValidTransition('executing', 'failed')).toBe(true);
  });

  it('allows blocked → classified', () => {
    expect(isValidTransition('blocked', 'classified')).toBe(true);
  });

  it('allows executing → waiting_for_user', () => {
    expect(isValidTransition('executing', 'waiting_for_user')).toBe(true);
  });

  it('allows budget_exhausted → completed', () => {
    expect(isValidTransition('budget_exhausted', 'completed')).toBe(true);
  });

  it('throws on invalid transition', () => {
    expect(() => validateTransition('created', 'completed')).toThrow();
  });
});
