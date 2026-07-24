# Governance Policy

## Levels

| Level | Classification | Examples |
|-------|---------------|----------|
| 0 | Read-only | read, glob, grep, search |
| 1 | Reversible repository | edit, write, npm install, git commit |
| 2 | External side-effect | git push, deploy, merge PR |
| 3 | Destructive/machine | sudo, reboot, shutdown, rm -rf / |

## Allowed by default
- Repository read operations
- Repository write operations
- Branch creation
- Local dependency install
- Running verification commands

## Requires approval
- Git push and PR merge
- Production deployment
- External service modification

## Denied
- sudo commands
- System reboot/shutdown
- Session termination
- Hardware/bios changes
- Path traversal
- Secret leakage

## Fail Closed

Protected actions fail closed. Non-critical telemetry fails open with logged failure.
