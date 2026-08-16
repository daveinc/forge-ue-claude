---
name: forge-init
description: Start a greenfield game through design interview, compact GDD, and parallel production DAGs
---

<invocation>
- Invoked by naming `forge-init`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Turn an idea into approved, schedulable studio work, then hand control to GSD's persisted phase loop.

Delegation: relay. Orchestrator role: run the entry gate, conduct the interview, compile the DAGs, then stop. Project inception only — never an execution phase.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-init.md
@<gsd-core>/workflows/new-project.md
@<forge-plugin-root>/references/delegation-contract.md
@<forge-plugin-root>/skills/forge-init/references/gsd-lifecycle.md
@<forge-plugin-root>/skills/forge-init/references/project-inception.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (entry gate, one question at a time, human approval of visual direction, packet registration, stop boundary).
</process>
