# Python Runtime File Disposition

Audit of every Heidi-related Python file in `opencode-agent-pack/scripts/`.

| File | Purpose | Phase 1 Status | Phase 2 Plan |
|------|---------|---------------|--------------|
| `strategy_selector.py` | Routing classification | Retain as compatibility adapter; new logic in TypeScript | Remove when TS classifier is stable |
| `token_budget.py` | Token budget manager | Retain for diagnostics CI; Phase 1 budget is advisory | Migrate to BudgetGate |
| `token_estimator.py` | Token estimation | Retain for CI benchmarking | Migrate to PricingResolver |
| `delegation_handoff.py` | Compact handoff builder | Prompt-level only in Phase 1 | Migrate to DelegationContract |
| `context_memory.py` | Repository context index | Retain for caching | Migrate to context/engine |
| `runtime_doctor.py` | Diagnostic checks | Partial: new TS doctor covers governance, routing, DB | Migrate remaining checks |
| `task_ledger.py` | Task record keeping | Replaced by `storage/database.ts` | Remove |
| `gen-prompts.py` | Prompt generation | Retain for prompt rebuild | Migrate to build-time tool |
| `proactive_audit.py` | Pre-commit audit | Retain for CI | Merge into audit-runner |
| `benchmark.py` | Benchmark runner | Retain for CI | Keep as benchmark tool |
| `migrate.py` | Migration helper | Retain | Keep |
| `prompt_consistency.py` | Prompt validation | Retain (used by TS doctor) | Keep as cross-check |
| `memory.py` | Memory validation | Retain | Keep |
| `prompt_proposals.py` | Prompt proposals | Retain | Keep |
| `failure_classifier.py` | Error classification | Retain | Keep |
| `fast_path.py` | Fast path check | Retain | Keep |

## Classification Summary

1. **Migrate to TypeScript** (6): strategy_selector, token_budget, token_estimator, delegation_handoff, context_memory, runtime_doctor (partial)
2. **Retain as compatibility adapter** (3): strategy_selector, runtime_doctor, prompt_consistency
3. **Retain for diagnostics/CI** (7): benchmark, memory, prompt_proposals, failure_classifier, fast_path, gen-prompts, proactive_audit
4. **Remove as dead/misleading** (1): task_ledger (replaced by database.ts)
