# Routing

## Strategies

| Strategy | When | Delegation |
|----------|------|------------|
| `fast_path` | Typo, comment, single-constant, trivial CSS | None |
| `direct` | Default — single-domain, non-sensitive | None |
| `single_specialist` | One domain requires expertise | 1 specialist |
| `parallel_specialists` | Two independent domains | 2 specialists |
| `audit_only` | Read-only review requested | 1 auditor |
| `debug_investigation` | CI failure, bug, crash | 1 debugger |
| `planning_only` | Architecture, roadmap | 1 planner |
| `blocked_for_user_action` | Machine-level change requires user | None |

## Classification Inputs

- Task text (tokens + exact phrases)
- User-requested agent
- File discovery confidence
- Task ambiguity score
- Expected file count
- Independent parallel work flag
- Verification complexity

## False Trigger Prevention

The following are explicitly NOT delegation triggers:
- Word "review" alone → only exact phrase "code review", "security review"
- Word "config" → not a disqualifier
- Word "plugin" → not a disqualifier
- Word "CI" → only if combined with "failure", "pipeline failure", "failing"
- File count alone → no automatic delegation
