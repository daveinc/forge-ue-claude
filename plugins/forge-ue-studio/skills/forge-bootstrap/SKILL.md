---
name: forge-bootstrap
description: Install or resume the project-local Forge control plane and its installation checks
---

<invocation>
- Invoked by naming `forge-bootstrap`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Create the durable project control plane before design or Unreal work.

Delegation: native, with delegated investigation jobs. Orchestrator role: install the overlay, compile and dispatch installation jobs by wave, verify independently, then run the closure gate.
</objective>

<flags>
- `--resume` — continue an incomplete bootstrap from persisted state.

A flag is active only when its literal token appears in `{{FORGE_ARGS}}`. Never infer that a flag is active because it is documented here.
</flags>

<execution_context>
@<forge-plugin-root>/workflows/forge-bootstrap.md
@<forge-plugin-root>/skills/forge-bootstrap/references/installation-waves.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (reversible install, wave dispatch, independent verification, the bootstrap gate, stop boundaries).
</process>
