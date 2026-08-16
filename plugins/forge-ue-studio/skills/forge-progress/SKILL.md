---
name: forge-progress
description: Report phase state, execution coverage, and the next action
---

<invocation>
- Invoked by naming `forge-progress`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Report where the project stands.

Delegation: contain. Orchestrator role: contain GSD's progress reporting, then add Forge's execution-coverage and capability-staleness views. Never mutates phase state.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-progress.md
@<gsd-core>/workflows/progress.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (read-only reporting, coverage and staleness reporting).
</process>
