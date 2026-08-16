---
name: forge-execute-phase
description: Execute the plans in a phase under Unreal lane control
---

<invocation>
- Invoked by naming `forge-execute-phase`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Run approved plans with the write-lock and lane leases held around GSD's executor.

Delegation: contain. Orchestrator role: resolve capabilities to lanes, acquire leases, route each plan, then release everything.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-execute-phase.md
@<gsd-core>/workflows/execute-phase.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (lane resolution, lease acquisition and release, worktree isolation, fallback recording).
</process>
