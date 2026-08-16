# Forge Review — workflow

## PRE — Forge

1. Resolve the scope. Default to the active phase from Forge Next; an explicit phase argument overrides it.
2. Load `.forge/acceptance/registry.json` and grade against the registered suites.
3. Load `.forge/capabilities/qualifications.json` and note which routes carry evidence, under which host.
4. Choose the reviewer. Default to the resident host. Use a qualified optional worker only when independence or economy justifies it and its qualification covers the exact task class and complexity tier.
5. Hand the reviewer the requirements, the artifact or diff, acceptance criteria, and evidence. **Never pass builder reasoning.**

## CORE — GSD

1. Contain one workflow per requested mode: no flag runs `review.md` against the active phase plan, `--code` runs `code-review.md` against source changed during the phase, `--security` runs `secure-phase.md` against the plan's threat model, `--audit` runs `audit-uat.md` across phases. Give each subagent the scope, acceptance criteria, and artifacts only.
2. Require a structured result from each: findings with severity, the evidence behind each, and an explicit verdict. Merge multiple modes into one verdict.

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
