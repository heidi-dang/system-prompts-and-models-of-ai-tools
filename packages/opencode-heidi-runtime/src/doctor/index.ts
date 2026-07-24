#!/usr/bin/env node
/**
 * Runtime doctor — diagnostic entry point.
 */

import { DoctorChecks } from './checks.js';
import { RuntimeDatabase } from '../storage/database.js';
import { resolveDbPath } from '../config/loader.js';

const args = process.argv.slice(2);
const mode = args.includes('--installed') ? 'installed' : 'isolated';
const db = new RuntimeDatabase(resolveDbPath('/tmp/heidi-runtime-doctor.db'));

const checks = new DoctorChecks(db);
const results = checks.runAll(mode === 'installed');

let passes = 0;
let fails = 0;
let skips = 0;

for (const r of results) {
  console.log(`${r.status}: ${r.label}${r.detail ? ` (${r.detail})` : ''}`);
  if (r.status === 'PASS') passes++;
  if (r.status === 'FAIL') fails++;
  if (r.status === 'SKIP') skips++;
}

console.log(`\nSummary: ${passes} PASS, ${fails} FAIL, ${skips} SKIP`);
console.log(JSON.stringify({ passes, fails, skips, results, mode }));

db.close();

// Exit non-zero on any FAIL
process.exit(fails > 0 ? 1 : 0);
