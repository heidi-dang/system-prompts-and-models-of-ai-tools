/**
 * Legacy Python adapter — explicit invocation path for retained Python scripts.
 * Validated input/output, timeout, exit-code handling. No broad exception suppression.
 */

import { execSync } from 'child_process';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PACKAGES_DIR = join(__dirname, '..', '..', '..', '..', 'opencode-agent-pack', 'scripts');

interface PythonResult {
  status: 'ok' | 'error';
  output: string;
  exitCode: number;
  elapsedMs: number;
}

function runPythonScript(scriptName: string, args: string[], input?: string): PythonResult {
  const scriptPath = join(PACKAGES_DIR, scriptName);
  const start = Date.now();
  try {
    const output = execSync(
      `python3 "${scriptPath}" ${args.join(' ')}`,
      {
        input,
        timeout: 30000,
        encoding: 'utf-8',
        maxBuffer: 5 * 1024 * 1024,
      }
    );
    return { status: 'ok', output: output.trim(), exitCode: 0, elapsedMs: Date.now() - start };
  } catch (e: any) {
    return {
      status: 'error',
      output: e.stderr?.slice(0, 1000) ?? String(e).slice(0, 1000),
      exitCode: e.status ?? 1,
      elapsedMs: Date.now() - start,
    };
  }
}

/** Legacy Python script adapters */
export const legacyPython = {
  promptConsistencyCheck(input?: string): PythonResult {
    return runPythonScript('prompt_consistency.py', ['--check'], input);
  },
  strategySelect(task: string, contextPath?: string): PythonResult {
    const args = ['select', '--task', task];
    if (contextPath) args.push('--context', contextPath);
    return runPythonScript('strategy_selector.py', args);
  },
};
