---
name: forge-spec-phase
description: Clarify what a phase delivers, with ambiguity scoring, before discussion
---

<invocation>
- Invoked by naming `forge-spec-phase`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Resolve a vague or contested phase goal into a scored specification.

Delegation: relay. Orchestrator role: score ambiguity against the GDD ledger, relay GSD's spec workflow, then re-grade interface ambiguity.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-spec-phase.md
@<gsd-core>/workflows/spec-phase.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (ambiguity scoring against settled decisions, interface severity override).
</process>
