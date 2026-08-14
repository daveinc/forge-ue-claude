---
name: forge-quality-gate
description: Design acceptance coverage, independently review attempts, and prevent unsupported completion claims across Unreal code, assets, service boundaries, builds, performance, and release work. Use when defining tests, reviewing a result, checking regression risk, accepting a work order, promoting an asset, or claiming a phase complete.
---

# Forge Quality Gate

Require fresh evidence before accepting work.

## Workflow

1. Read the requirement, work packet, artifact/diff, acceptance registry, route contract and returned evidence. Do not read builder reasoning unless investigating a failure after the independent pass.
2. Select the smallest sufficient test layers: schema/static, unit, contract, integration, editor/commandlet, PIE/runtime, asset structural, performance, cook/package, platform, visual and human subjective.
3. Audit missing regression coverage, boundary compatibility, bad-input behavior, idempotency, rollback, stale references, and seeded-bad rejection—not only currently failing tests.
4. Run fresh verification commands or inspect fresh tool-produced evidence. Separate observed facts, inferences, uncertainties and residual risk.
5. Return the attempt-result contract from [result-contract.md](references/result-contract.md), with findings ordered by severity.
6. Accept only when every required criterion has current evidence and required human gates are signed. A review finding never grants permission to apply its own fix.
7. On `FAIL`, `PARTIAL`, `BLOCKED` or `INDETERMINATE`, preserve the attempt and route the next action through `$forge-route-work` or `$forge-retrospective`.

Never replace human decisions for primary art direction, likeness, appeal, game feel or release responsibility.
