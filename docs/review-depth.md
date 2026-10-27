# Review Depth Guidelines

To keep PRs small and ensure appropriate review rigor, scale review depth based on PR size and risk.

## Size-based guidelines

Size labels are applied automatically by the `size-label` workflow:

| Size | Changes | Review depth |
|---|---|---|
| `size/XS` | ≤10 lines | Quick review - focus on correctness |
| `size/S` | ≤50 lines | Standard review - check logic and tests |
| `size/M` | ≤200 lines | Thorough review - check design, tests, edge cases |
| `size/L` | ≤500 lines | Deep review - may require discussion, consider splitting |
| `size/XL` | >500 lines | **Requires justification** - strongly consider splitting. Deep review required. |

## Risk-based escalation

The following areas **always get deep review** regardless of size:

- **Billing/payments** - Financial impact
- **Authentication/authorization** - Security critical
- **Migrations** - Database/schema changes
- **Secrets/credentials** - Security sensitive
- **Protected paths** (`AGENTS.md`, `agents/**`, CI config, lockfiles) - Require person review per factory rules
- **Infrastructure/deployment** - Production impact

## Large diffs and protected paths

Per factory policy:
- **Large diffs** (size/L or size/XL) require careful review and strong justification. PR authors should prefer smaller, focused PRs.
- **Protected paths** go to a person (Scott) - agents cannot approve/merge changes to protected paths without explicit human review.
- **Issue Shipper/builder guidance:** Keep PRs small and focused. If a change would be large, split it into multiple PRs where possible.

## Review process

1. Check size label and assess risk
2. For high-risk areas, do a deep review even if small
3. For large PRs (>L) without strong justification, request splitting
4. Protected paths always require human review
