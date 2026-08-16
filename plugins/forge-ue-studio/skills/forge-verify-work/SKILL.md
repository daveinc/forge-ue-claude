---
name: forge-verify-work
description: Validate completed work through UAT plus in-engine evidence
---

<invocation>
- Invoked by naming `forge-verify-work`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Confirm a phase actually works in the engine, not only in the test suite.

Delegation: relay. Orchestrator role: grade against registered acceptance suites, relay GSD's UAT session, then require in-engine evidence.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-verify-work.md
@<gsd-core>/workflows/verify-work.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (acceptance-suite grading, single verification authority, in-engine evidence, human feel gates).
</process>
