---
name: forge-phase
description: Add, insert, remove, or edit phases in the roadmap
---

<invocation>
- Invoked by naming `forge-phase`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Change the plan of record.

Delegation: run. Orchestrator role: load the packet registry, run GSD's phase CRUD, then verify no canonical packet ID was replaced.
</objective>

<flags>
- `--insert` — insert a phase between existing ones.
- `--remove` — remove a phase.
- `--edit` — edit an existing phase.

A flag is active only when its literal token appears in `{{FORGE_ARGS}}`. Never infer that a flag is active because it is documented here.
</flags>

<execution_context>
@<forge-plugin-root>/workflows/forge-phase.md
@<gsd-core>/workflows/add-phase.md
@<gsd-core>/workflows/insert-phase.md
@<gsd-core>/workflows/remove-phase.md
@<gsd-core>/workflows/edit-phase.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (packet-ID immutability, alias and provenance records).
</process>
