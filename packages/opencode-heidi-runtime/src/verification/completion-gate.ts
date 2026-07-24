/**
 * Completion gate — validates that a task meets completion requirements.
 */

export interface CompletionCheck {
  hasRequiredChanges: boolean;
  requiredVerificationRan: boolean;
  mandatoryVerificationPassed: boolean;
  hasUnrelatedDrift: boolean;
  hasRemainingFailures: boolean;
  confidence: number;
  details: string[];
}

export class CompletionGate {
  check(task: { status: string; strategy?: string }, verifications: Array<{ status: string; category: string }>): CompletionCheck {
    const details: string[] = [];
    const hasRequiredChanges = task.status !== 'created';
    if (!hasRequiredChanges) details.push('no changes detected');

    const requiredCategories = ['lint', 'typecheck', 'test', 'build'];
    const applicableCategories = this.getApplicableCategories(task.strategy);

    const ranRequired = applicableCategories.every(cat =>
      verifications.some(v => v.category === cat)
    );
    if (!ranRequired) details.push('not all required verification categories ran');

    const failures = verifications.filter(v => v.status === 'fail');
    const hasFailedVerifications = failures.length > 0;
    if (hasFailedVerifications) details.push(`${failures.length} verification(s) failed`);

    const confidence = this.calculateConfidence(hasRequiredChanges, ranRequired, hasFailedVerifications);

    return {
      hasRequiredChanges,
      requiredVerificationRan: ranRequired,
      mandatoryVerificationPassed: !hasFailedVerifications,
      hasUnrelatedDrift: false,
      hasRemainingFailures: hasFailedVerifications,
      confidence,
      details,
    };
  }

  private getApplicableCategories(strategy?: string): string[] {
    if (strategy === 'fast_path') return ['lint'];
    if (strategy === 'audit_only') return [];
    if (strategy === 'debug_investigation') return ['test'];
    return ['lint', 'typecheck', 'test'];
  }

  private calculateConfidence(hasChanges: boolean, verifRan: boolean, hasFailures: boolean): number {
    if (!hasChanges) return 0;
    if (hasFailures) return 0.3;
    if (!verifRan) return 0.5;
    return 0.95;
  }
}
