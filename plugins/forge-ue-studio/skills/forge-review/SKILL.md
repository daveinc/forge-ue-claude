---
name: forge-review
description: Review game project work — plans, code, security, or outstanding UAT — against Forge's acceptance registry and capability qualification rather than generic criteria. Use before executing a non-trivial plan, after implementation lands, when threat mitigations need verifying, or when auditing what is still unverified across phases.
---

# Forge Review

One review verb with four modes. Each fans out to the GSD workflow that does the reviewing, then grades the result against Forge's own standards — the acceptance registry, capability qualification evidence, and the lane contract — instead of a generic definition of quality.

Delegation mode: **contain** — spawn a subagent to read and follow the stock GSD workflow, and require a structured result. The subagent never talks to the user.

Read [delegation-contract.md](../../references/delegation-contract.md) first. It defines the PRE / CORE / POST shape and the rules not repeated here.

## Modes

| Invocation | GSD workflow | Reviews |
|---|---|---|
| `forge-review` (default) | `review.md` | The active phase plan, before execution |
| `forge-review --code` | `code-review.md` | Source changed during the phase |
| `forge-review --security` | `secure-phase.md` | Threat mitigations from the plan's threat model |
| `forge-review --audit` | `audit-uat.md` | Outstanding UAT and verification items across phases |

Modes compose. `--code --security` runs both and returns one merged verdict.

## PRE — Forge

1. Resolve the scope. Default is the active phase from Forge Next; an explicit phase argument overrides it.
2. Load `.forge/acceptance/registry.json`. **The registered acceptance suites are the grading rubric.** A review that passes generic criteria but fails a registered suite has not passed.
3. Load `.forge/capabilities/qualifications.json`. Note which routes carry evidence and under which host.
4. Choose the reviewer. The resident host reviews by default. A qualified optional worker may review only when independence or economy justifies it *and* its qualification covers the exact task class and complexity tier.
5. Enforce reviewer independence: hand over requirements, the artifact or diff, acceptance criteria, and evidence. **Never pass builder reasoning.** A reviewer that has seen the builder's rationale is no longer independent.

## CORE — GSD

1. Contain the workflow for each requested mode. Give the subagent the scope, the acceptance criteria, and the artifacts — nothing else.
2. Require a structured result: findings with severity, the evidence behind each, and an explicit verdict. Not prose.

## POST — Forge

1. Grade findings against the acceptance registry, not only against the reviewer's own severity. A finding that breaks a registered suite is blocking regardless of how the reviewer scored it.
2. Apply the game-specific checks GSD has no notion of:
   - a change touching Unreal content must have declared the project-exclusive lane
   - a change to a registered asset interface must be flagged, because it invalidates parallel visual work
   - placeholder art is acceptable; an undeclared interface change is not
3. Reject any offload route whose qualification was recorded under a different runtime host. That evidence is stale and the review must be re-run on the resident host.
4. Record the cycle in `.forge/reviews/registry.json` with the reviewer, the mode, the evidence, and residual risk.
5. Return a verdict of `PASS`, `CHANGES_REQUIRED`, or `ESCALATE`. Escalate on a stalled concern count or when the convergence cycle limit is reached — do not keep looping.

## Boundaries

- Review is bounded. Cycles have a limit; a stall escalates to a human rather than iterating.
- Never auto-apply fixes from a review in the same pass that produced them. Findings are input to a plan, not a licence to edit.
- Subjective art and game feel are human gates. A reviewer may report on them but never closes them.
- For plan convergence specifically, prefer `forge-plan-convergence` — it owns the bounded source-grounded cycle. This skill's default mode is a single review pass, not a convergence loop.
