---
name: forge-onboard
description: Onboard an existing Unreal project into Forge and GSD planning
---

<invocation>
- Invoked by naming `forge-onboard`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Adopt a codebase that has no planning state.

Delegation: run. Orchestrator role: establish capability routes first, run GSD's onboarding, then extend the map into Unreal-specific structure.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-onboard.md
@<gsd-core>/workflows/onboard.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (capability-first ordering, Unreal structure coverage, asset-interface registration).
</process>
