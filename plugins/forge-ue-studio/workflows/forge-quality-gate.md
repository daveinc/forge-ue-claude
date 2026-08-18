<!-- forge:workflow
name: quality-gate
consumes: requirement, work packet, artifact or diff, .forge/acceptance/registry.json, route contract, returned evidence
produces: attempt-result contract with findings ordered by severity
-->

# Forge Quality Gate — workflow

<purpose>
Grade returned work against acceptance evidence and return a typed attempt result.
</purpose>

<core_principle>
Never let a review finding grant permission to apply its own fix. Never replace a human decision on
primary art direction, likeness, appeal, game feel or release.
</core_principle>

<process>

1. Read the requirement, work packet, artifact or diff, acceptance registry, route contract, and returned evidence. Read builder reasoning only when investigating a failure after the independent pass.
2. Select the smallest sufficient test layers from schema/static, unit, contract, integration, editor/commandlet, PIE/runtime, asset structural, performance, cook/package, platform, visual, and human subjective.
3. Audit missing regression coverage, boundary compatibility, bad-input behaviour, idempotency, rollback, stale references, and seeded-bad rejection.
4. Run fresh verification commands or inspect fresh tool-produced evidence. Separate observed facts, inferences, uncertainties, and residual risk.
5. Run GSD's `validate-phase.md` when asked to fill validation gaps for a completed phase, and `add-tests.md` when asked to generate tests from its UAT criteria. Require a structured result from each, and grade it through steps 1–4.
6. Return the attempt-result contract from [result-contract.md](../skills/forge-quality-gate/references/result-contract.md), findings ordered by severity.
7. Accept only when every required criterion has current evidence and every required human gate is signed. Never let a review finding grant permission to apply its own fix.
8. On `FAIL`, `PARTIAL`, `BLOCKED`, or `INDETERMINATE`, preserve the attempt and route the next action through `forge-route-work` or `forge-retrospective`.
9. Never replace a human decision on primary art direction, likeness, appeal, game feel, or release.

</process>
