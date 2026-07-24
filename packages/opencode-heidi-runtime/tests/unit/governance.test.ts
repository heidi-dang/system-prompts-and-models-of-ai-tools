import { describe, it, expect } from 'vitest';
import { PolicyEngine } from '../../src/governance/policy-engine.js';
import { CommandPolicy } from '../../src/governance/command-policy.js';
import { redact } from '../../src/governance/redaction.js';

describe('PolicyEngine', () => {
  const engine = new PolicyEngine();

  it('allows read-only tools', () => {
    expect(engine.evaluateTool('read', { filePath: 'src/index.ts' }, 't1').result).toBe('allow');
    expect(engine.evaluateTool('glob', { pattern: '*.ts' }, 't1').result).toBe('allow');
  });

  it('denies dangerous tools', () => {
    const d = engine.evaluateTool('delete_file', { filePath: '/etc/passwd' }, 't1');
    expect(d.result).toBe('deny');
    expect(d.policyLevel).toBe(3);
  });

  it('blocks path traversal', () => {
    const d = engine.evaluateTool('edit', { filePath: '../../etc/passwd' }, 't1');
    expect(d.result).toBe('deny');
  });
});

describe('CommandPolicy', () => {
  const policy = new CommandPolicy();

  it('denies sudo commands', () => {
    const d = policy.evaluate('sudo rm -rf /var/log', 't1', 'heidi');
    expect(d.result).toBe('deny');
    expect(d.policyLevel).toBe(3);
  });

  it('denies shutdown', () => {
    const d = policy.evaluate('shutdown -h now', 't1', 'heidi');
    expect(d.result).toBe('deny');
  });

  it('denies reboot', () => {
    const d = policy.evaluate('reboot', 't1', 'heidi');
    expect(d.result).toBe('deny');
  });

  it('allows npm install', () => {
    const d = policy.evaluate('npm install express', 't1', 'heidi');
    expect(d.result).toBe('allow');
    expect(d.policyLevel).toBe(1);
  });

  it('allows pip install', () => {
    const d = policy.evaluate('pip install flask', 't1', 'heidi');
    expect(d.result).toBe('allow');
  });

  it('allows git commit', () => {
    const d = policy.evaluate('git add . && git commit -m "fix"', 't1', 'heidi');
    expect(d.result).toBe('allow');
  });

  it('requires approval for git push', () => {
    const d = policy.evaluate('git push origin main', 't1', 'heidi');
    expect(d.result).toBe('approval_required');
    expect(d.policyLevel).toBe(2);
  });

  it('requires approval for deploy', () => {
    const d = policy.evaluate('npm run deploy --production', 't1', 'heidi');
    expect(d.result).toBe('approval_required');
  });

  it('normalizes commands', () => {
    expect(policy.normalize('npm install --save-dev express').includes('npm install')).toBe(true);
  });
});

describe('Redaction', () => {
  it('redacts API keys', () => {
    const result = redact('API_KEY=sk-abc123def456xyz789');
    expect(result).toContain('[REDACTED]');
    expect(result).not.toContain('sk-abc123');
  });

  it('redacts GitHub tokens', () => {
    const result = redact('token=ghp_abc123def456ghi789jkl012');
    expect(result).toContain('[REDACTED]');
  });

  it('redacts Bearer tokens', () => {
    const result = redact('Authorization: Bearer eyJhbGciOiJIUzI1NiJ9');
    expect(result).toContain('[REDACTED]');
  });

  it('returns non-sensitive text unchanged structure', () => {
    const result = redact('hello world');
    expect(result).toContain('hello');
  });
});
