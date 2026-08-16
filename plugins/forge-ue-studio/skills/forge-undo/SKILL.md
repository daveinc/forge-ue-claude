---
name: forge-undo
description: Roll back a phase or plan when execution went wrong
---

<invocation>
- Invoked by naming `forge-undo`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Revert committed work safely.

Delegation: run. Orchestrator role: check locks and dependants, run GSD's undo, then confirm the project still opens.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-undo.md
@<gsd-core>/workflows/undo.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (lock safety, dependency check, post-revert editor check).
</process>
