---
name: forge-handoff
description: Pause work before a context reset without losing state
---

<invocation>
- Invoked by naming `forge-handoff`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Persist everything the next session needs.

Delegation: contain. Orchestrator role: contain GSD's pause workflow, then persist leases, editor state, and the producing host.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-handoff.md
@<gsd-core>/workflows/pause-work.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (lease and editor-state persistence, host recording).
</process>
