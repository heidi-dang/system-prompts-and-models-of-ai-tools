import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { homedir } from 'os';
import { join, dirname } from 'path';
import { HeidiRuntimeOptions, type HeidiRuntimeConfig, DEFAULT_CONFIG } from './schema.js';

export function resolveDbPath(customPath?: string): string {
  if (customPath) return customPath;
  const base = process.env.OPENCODE_CONFIG_DIR
    ? process.env.OPENCODE_CONFIG_DIR
    : join(homedir(), '.config', 'opencode');
  const runtimeDir = join(base, 'heidi-runtime');
  if (!existsSync(runtimeDir)) {
    mkdirSync(runtimeDir, { recursive: true });
  }
  return join(runtimeDir, 'runtime.db');
}

export function loadConfig(path?: string): HeidiRuntimeConfig {
  if (!path) return { ...DEFAULT_CONFIG };
  try {
    const raw = readFileSync(path, 'utf-8');
    const parsed = JSON.parse(raw);
    const result = HeidiRuntimeOptions.safeParse(parsed);
    if (result.success) return result.data;
    console.warn('[heidi-runtime] config validation failed, using defaults:', result.error.message);
    return { ...DEFAULT_CONFIG };
  } catch {
    return { ...DEFAULT_CONFIG };
  }
}
