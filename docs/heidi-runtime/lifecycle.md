# Task Lifecycle

## State Machine

```
created → classified → context_ready → executing → verifying → completed
                                              ↘ blocked / failed / cancelled / budget_exhausted / waiting_for_user
                          verifying → executing (rework)
                          verifying → partially_completed
                          blocked → classified / executing / cancelled
```

## States

| State | Meaning |
|-------|---------|
| `created` | Task created from user message |
| `classified` | Routing decision recorded |
| `context_ready` | Context pack assembled |
| `executing` | Implementation in progress |
| `verifying` | Verification running |
| `completed` | All acceptance criteria met |
| `blocked` | Waiting for user or dependency |
| `failed` | Irrecoverable failure |
| `cancelled` | Explicitly cancelled |
| `budget_exhausted` | Phase 2 budget limit reached |
| `waiting_for_user` | User input required |
| `partially_completed` | Some work done, some remaining |

## Transitions

All transitions are validated. Invalid transitions throw. Checkpoints are saved at each transition.
