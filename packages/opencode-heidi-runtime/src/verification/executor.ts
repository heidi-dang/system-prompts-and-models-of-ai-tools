/**
 * Verification executor — runs proportionate verification commands.
 */

import { execSync } from 'child_process';
import { createHash } from 'crypto';

export interface VerificationResult {
  command: string;
  category: string;
  exitCode: number;
  outputDigest: string;
  status: 'pass' | 'fail' | 'skipped';
  error?: string;
  workingDirectory?: string;
}

export interface VerificationPlan {
  categories: string[];
  commands: Array<{ command: string; category: string; workingDirectory?: string }>;
}

export class VerificationEngine {
  async run(command: string, category: string, workingDirectory?: string): Promise<VerificationResult> {
    const startTime = Date.now();
    try {
      const output = execSync(command, {
        cwd: workingDirectory ?? process.cwd(),
        timeout: 120_000,
        encoding: 'utf-8',
        maxBuffer: 10 * 1024 * 1024,
      });
      const digest = createHash('sha256').update(output).digest('hex').slice(0, 16);
      return {
        command,
        category,
        exitCode: 0,
        outputDigest: digest,
        status: 'pass',
        workingDirectory,
      };
    } catch (e: any) {
      const stderr = e.stderr ?? e.message ?? String(e);
      const digest = createHash('sha256').update(stderr).digest('hex').slice(0, 16);
      return {
        command,
        category,
        exitCode: e.status ?? 1,
        outputDigest: digest,
        status: 'fail',
        error: stderr.slice(0, 500),
        workingDirectory,
      };
    }
  }
}
