---
name: forge-discuss-phase
description: Gather phase context through adaptive questioning before planning
---

<invocation>
- Invoked by naming `forge-discuss-phase`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Settle the gameplay and art decisions a phase needs before a plan exists.

Delegation: relay. Orchestrator role: scope questions to the departments in play, reframe each in game terms, and pass answers back down verbatim.
</objective>

<flags>
- `--assumptions` — codebase-first mode; best on an existing project.
- `--power` — batch every question in one pass.
- `--list-assumptions` — list the assumptions without asking.

A flag is active only when its literal token appears in `{{FORGE_ARGS}}`. Never infer that a flag is active because it is documented here.
</flags>

<execution_context>
@<forge-plugin-root>/workflows/forge-discuss-phase.md
@<gsd-core>/workflows/discuss-phase.md
@<gsd-core>/workflows/discuss-phase-assumptions.md
@<gsd-core>/workflows/discuss-phase-power.md
@<gsd-core>/workflows/list-phase-assumptions.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (one question at a time, game-dev reframing, unresolved-interface surfacing).
</process>
