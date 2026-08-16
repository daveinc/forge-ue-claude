---
name: forge-quality-gate
description: Design acceptance coverage, review attempts independently, and refuse unsupported completion claims
---

<invocation>
- Invoked by naming `forge-quality-gate`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Require fresh evidence before accepting work.

Delegation: contain for validation and test generation, native for grading. Orchestrator role: select test layers, run fresh verification, and return the attempt-result contract.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-quality-gate.md
@<gsd-core>/workflows/validate-phase.md
@<gsd-core>/workflows/add-tests.md
@<forge-plugin-root>/references/delegation-contract.md
@<forge-plugin-root>/skills/forge-quality-gate/references/result-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (evidence freshness, reviewer independence, human gates, attempt preservation).
</process>
