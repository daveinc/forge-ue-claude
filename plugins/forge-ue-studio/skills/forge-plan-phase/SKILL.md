---
name: forge-plan-phase
description: Create a phase plan declaring asset interfaces, required lanes, and mutation risk
---

<invocation>
- Invoked by naming `forge-plan-phase`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Turn a discussed phase into executable plans.

Delegation: contain. Orchestrator role: apply Forge preconditions, contain GSD's planner, then reject any plan that cannot be routed safely.
</objective>

<flags>
- `--dependencies` — detect file overlap between phases and feed the lane leases.

A flag is active only when its literal token appears in `{{FORGE_ARGS}}`. Never infer that a flag is active because it is documented here.
</flags>

<execution_context>
@<forge-plugin-root>/workflows/forge-plan-phase.md
@<gsd-core>/workflows/plan-phase.md
@<gsd-core>/workflows/analyze-dependencies.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (lane declaration, packet-ID reuse, asset-interface registration, convergence before execution).
</process>
