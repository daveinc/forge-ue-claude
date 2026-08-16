---
name: forge-map-codebase
description: Analyse an Unreal codebase and produce structured planning intel
---

<invocation>
- Invoked by naming `forge-map-codebase`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Map unfamiliar or inherited code before planning against it.

Delegation: run. Orchestrator role: run GSD's mappers, then add Unreal-specific structure.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-map-codebase.md
@<gsd-core>/workflows/map-codebase.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (Unreal module, Blueprint, and binary-asset coverage).
</process>
