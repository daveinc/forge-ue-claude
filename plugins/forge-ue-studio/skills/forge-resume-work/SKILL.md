---
name: forge-resume-work
description: Resume interrupted work from persisted state
---

<invocation>
- Invoked by naming `forge-resume-work`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Restart work from files after a context reset, fresh session, or handoff.

Delegation: contain. Orchestrator role: route through Forge Next, reclaim leases, contain GSD's resume workflow, then hand back to the recommended action.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-resume-work.md
@<gsd-core>/workflows/resume-project.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (file-sourced routing, lease reclamation, cross-host qualification staleness).
</process>
