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

Delegation: native for routing, run for phase execution. Orchestrator role: select work, resolve capabilities to lanes, isolate, dispatch, run GSD's executor under the held leases, and record every transition. Never owns implementation.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-route-work.md
@<gsd-core>/workflows/execute-phase.md
@<forge-plugin-root>/references/delegation-contract.md
@<forge-plugin-root>/skills/forge-route-work/references/routing.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (capability resolution, isolation selection, packet immutability, lease discipline, the Unreal write-lock held across GSD's executor, verifier independence).
</process>
