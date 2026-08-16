---
name: forge-route-work
description: Compile, rank, and dispatch bounded work packets across qualified studio lanes
---

<invocation>
- Invoked by naming `forge-route-work`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Fill the `studio-director` seat: compile approved decisions into bounded cross-department work and dispatch it.

Delegation: native. Orchestrator role: select work, resolve capabilities to lanes, isolate, dispatch, and record every transition. Never owns implementation.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-route-work.md
@<forge-plugin-root>/skills/forge-route-work/references/routing.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (capability resolution, isolation selection, packet immutability, lease discipline, verifier independence).
</process>
