---
name: forge-milestone
description: Start, complete, audit, or summarise a milestone
---

<invocation>
- Invoked by naming `forge-milestone`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Run the boundary between releases or vertical slices.

Delegation: run. Orchestrator role: confirm every phase verified, run the matching GSD workflow, then carry unresolved items forward.
</objective>

<flags>
- `--new` — start the next milestone.
- `--complete` — archive a finished milestone.
- `--audit` — audit completion against original intent.
- `--summary` — generate the milestone summary.
- `--plan-gaps` — turn audit findings into fix phases.

A flag is active only when its literal token appears in `{{FORGE_ARGS}}`. Never infer that a flag is active because it is documented here.
</flags>

<execution_context>
@<forge-plugin-root>/workflows/forge-milestone.md
@<gsd-core>/workflows/complete-milestone.md
@<gsd-core>/workflows/new-milestone.md
@<gsd-core>/workflows/audit-milestone.md
@<gsd-core>/workflows/milestone-summary.md
@<gsd-core>/workflows/plan-milestone-gaps.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (verification precondition, carry-forward of open decisions and unqualified routes).
</process>
