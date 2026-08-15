---
name: forge-review
description: Review a plan, code, security mitigations, or outstanding UAT against the acceptance registry and capability qualification. Use before executing a non-trivial plan, after implementation lands, or when auditing what is still unverified.
---

# Forge Review

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow and return a structured result. The subagent never talks to the user. The mode table below names the workflow per invocation.

Read [delegation-contract.md](../../references/delegation-contract.md) first.

## Modes

| Invocation | GSD workflow | Reviews |
|---|---|---|
| `forge-review` (default) | `review.md` | The active phase plan, before execution |
| `forge-review --code` | `code-review.md` | Source changed during the phase |
| `forge-review --security` | `secure-phase.md` | Threat mitigations from the plan's threat model |
| `forge-review --audit` | `audit-uat.md` | Outstanding UAT and verification items across phases |

Compose modes freely; `--code --security` returns one merged verdict.

## PRE — Forge

1. Resolve the scope. Default to the active phase from Forge Next; an explicit phase argument overrides it.
2. Load `.forge/acceptance/registry.json` and grade against the registered suites.
3. Load `.forge/capabilities/qualifications.json` and note which routes carry evidence, under which host.
4. Choose the reviewer. Default to the resident host. Use a qualified optional worker only when independence or economy justifies it and its qualification covers the exact task class and complexity tier.
5. Hand the reviewer the requirements, the artifact or diff, acceptance criteria, and evidence. **Never pass builder reasoning.**

## CORE — GSD

1. Contain the workflow for each requested mode. Give the subagent the scope, acceptance criteria, and artifacts only.
2. Require a structured result: findings with severity, the evidence behind each, and an explicit verdict.

## POST — Forge

1. Grade findings against the acceptance registry. Treat a finding that breaks a registered suite as blocking, whatever the reviewer scored it.
2. Apply Forge's own checks on the returned result:
   - flag a change touching Unreal content that declared no project-exclusive lane
   - flag a change to a registered asset interface, which invalidates parallel visual work
   - accept placeholder art; reject an undeclared interface change
3. Reject any offload route whose qualification was recorded under a different host, and re-run the review on the resident host.
4. Record the cycle in `.forge/reviews/registry.json` with the reviewer, mode, evidence, and residual risk.
5. Return `PASS`, `CHANGES_REQUIRED`, or `ESCALATE`. Escalate on a stalled concern count or the convergence cycle limit.

## Boundaries

- Never auto-apply a fix in the pass that produced the finding.
- Never close a subjective art or game-feel gate. Report on it and leave it to the human.
- For plan convergence, use `forge-plan-convergence`.
