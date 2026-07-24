import { describe, it, expect } from 'vitest';
import { classifyTask } from '../../src/routing/classifier.js';

describe('Routing classifier', () => {
  it('routes README typo to fast_path', () => {
    const r = classifyTask({
      taskText: 'fix typo in README',
      taskAmbiguity: 0.1,
      expectedFileCount: 1,
    });
    expect(r.strategy).toBe('fast_path');
    expect(r.confidence).toBeGreaterThan(0.5);
    expect(r.fallback).toBe(false);
  });

  it('routes comment correction to fast_path', () => {
    const r = classifyTask({
      taskText: 'correct spelling in documentation comment',
      taskAmbiguity: 0.1,
      expectedFileCount: 1,
    });
    expect(r.strategy).toBe('fast_path');
  });

  it('routes CI badge text to direct (not debugger)', () => {
    const r = classifyTask({
      taskText: 'update CI badge text in README',
    });
    expect(r.strategy).not.toBe('debug_investigation');
    expect(r.strategy).toBe('direct');
  });

  it('routes config wording typo to fast_path', () => {
    const r = classifyTask({
      taskText: 'fix config label typo in settings.toml',
      taskAmbiguity: 0.1,
      expectedFileCount: 1,
    });
    expect(r.strategy).toBe('fast_path');
  });

  it('routes plugin documentation edit to direct (not blocked)', () => {
    const r = classifyTask({
      taskText: 'update plugin documentation text',
    });
    expect(r.strategy).toBe('direct');
  });

  it('routes small frontend bug to direct or single_specialist', () => {
    const r = classifyTask({
      taskText: 'fix button alignment on profile page',
      expectedFileCount: 2,
    });
    expect(['direct', 'single_specialist']).toContain(r.strategy);
  });

  it('routes small backend bug to direct', () => {
    const r = classifyTask({
      taskText: 'fix API validation error',
    });
    expect(r.strategy).toBe('direct');
  });

  it('routes code review to audit_only', () => {
    const r = classifyTask({
      taskText: 'perform a code review of PR #42',
    });
    expect(r.strategy).toBe('audit_only');
  });

  it('routes security review to audit_only with high score', () => {
    const r = classifyTask({
      taskText: 'do a security review of the authentication module',
    });
    expect(r.strategy).toBe('audit_only');
    expect(r.score).toBeGreaterThanOrEqual(20);
  });

  it('routes CI failure to debug_investigation', () => {
    const r = classifyTask({
      taskText: 'fix failing CI pipeline',
    });
    expect(r.strategy).toBe('debug_investigation');
  });

  it('routes architecture plan to planning_only', () => {
    const r = classifyTask({
      taskText: 'create architecture plan for the project',
    });
    expect(r.strategy).toBe('planning_only');
  });

  it('routes ambiguous task to direct', () => {
    const r = classifyTask({
      taskText: 'improve the thing',
      taskAmbiguity: 0.7,
    });
    expect(r.strategy).toBe('direct');
  });

  it('routes machine-level change to blocked_for_user_action', () => {
    const r = classifyTask({
      taskText: 'restart the server after installing updates',
    });
    expect(r.strategy).toBe('blocked_for_user_action');
  });

  it('routes user-requested specialist', () => {
    const r = classifyTask({
      taskText: 'debug the production issue',
      userRequestedAgent: 'debugger',
    });
    // Should involve debug_investigation or direct
    expect(r.strategy).toBeTruthy();
  });

  it('does NOT route trivial doc review to auditor', () => {
    const r = classifyTask({
      taskText: 'review the wording of the error message',
    });
    expect(r.strategy).not.toBe('audit_only');
    expect(['fast_path', 'direct']).toContain(r.strategy);
  });

  it('routes full-stack feature with independent work to parallel_specialists', () => {
    const r = classifyTask({
      taskText: 'add frontend React component and backend API endpoint for user profiles',
      hasIndependentParallelWork: true,
    });
    expect(r.strategy).toBe('parallel_specialists');
  });

  it('records structured explanation for every route', () => {
    const r = classifyTask({ taskText: 'fix typo in README' });
    expect(r.signals).toBeDefined();
    expect(Array.isArray(r.signals)).toBe(true);
    expect(r.signals.length).toBeGreaterThanOrEqual(1);
  });
});
