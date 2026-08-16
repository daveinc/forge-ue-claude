---
name: forge-mvp-phase
description: Plan a phase as the thinnest playable vertical slice, and split it when too big
---

<invocation>
- Invoked by naming `forge-mvp-phase`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Reduce a phase to a loop a player can actually run.

Delegation: relay. Orchestrator role: define what playable means for this slice, relay GSD's MVP workflow, then register acceptance and asset interfaces.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-mvp-phase.md
@<gsd-core>/workflows/mvp-phase.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (playable definition, split judgement, feel gate, placeholder budget).
</process>
