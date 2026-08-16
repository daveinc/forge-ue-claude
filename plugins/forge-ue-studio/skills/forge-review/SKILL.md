---
name: forge-review
description: Review a plan, code, security mitigations, or outstanding UAT against the acceptance registry
---

<invocation>
- Invoked by naming `forge-review`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
One review verb with four modes, each graded against Forge's own standards.

Delegation: contain. Orchestrator role: pick an independent reviewer, contain the matching GSD workflow, then grade findings against the acceptance registry.
</objective>

<flags>
- `--code` — review source changed during the phase.
- `--security` — verify threat mitigations from the plan's threat model.
- `--audit` — audit outstanding UAT and verification items across phases.
- Modes compose; `--code --security` returns one merged verdict.

A flag is active only when its literal token appears in `{{FORGE_ARGS}}`. Never infer that a flag is active because it is documented here.
</flags>

<execution_context>
@<forge-plugin-root>/workflows/forge-review.md
@<gsd-core>/workflows/review.md
@<gsd-core>/workflows/code-review.md
@<gsd-core>/workflows/secure-phase.md
@<gsd-core>/workflows/audit-uat.md
@<gsd-core>/workflows/audit-fix.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (reviewer independence, acceptance grading, host-scoped qualification, cycle bounds).
</process>
