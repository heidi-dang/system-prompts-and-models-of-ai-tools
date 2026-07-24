/**
 * Secret redaction — removes sensitive values from telemetry and logs.
 */

const SENSITIVE_PATTERNS: RegExp[] = [
  /(?:api[_-]?key|apikey|secret|password|token|auth|credential)\s*[:=]\s*['"]?[A-Za-z0-9_\-\.]{8,}['"]?/gi,
  /(?:ghp_|gho_|ghu_|ghs_|ghr_)[A-Za-z0-9_]{36,}/gi,  // GitHub tokens
  /sk-[A-Za-z0-9]{32,}/gi,  // OpenAI keys
  /pk-[A-Za-z0-9]{32,}/gi,  // OpenAI publishable keys
  /-----BEGIN (RSA |EC )?PRIVATE KEY-----[\s\S]*?-----END (RSA |EC )?PRIVATE KEY-----/g,
  /(?:Bearer|Basic)\s+[A-Za-z0-9_\-\.]{10,}/gi,
];

export function redact(text: string): string {
  let result = text;
  for (const pattern of SENSITIVE_PATTERNS) {
    result = result.replace(pattern, '[REDACTED]');
  }
  return result;
}

export function isPotentiallySensitive(filePath: string): boolean {
  const sensitiveFiles = [
    '.env', '.env.local', '.env.production', '.env.development',
    'id_rsa', 'id_ed25519', '.netrc', '.npmrc',
    'credentials.json', 'service-account.json', 'secrets.json',
    'config.yml', 'config.yaml', '.envrc',
  ];
  const lower = filePath.toLowerCase();
  return sensitiveFiles.some(f => lower.includes(f));
}
