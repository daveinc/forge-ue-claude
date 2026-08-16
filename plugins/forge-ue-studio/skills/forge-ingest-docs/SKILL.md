---
name: forge-ingest-docs
description: Ingest existing design documents into planning state
---

<invocation>
- Invoked by naming `forge-ingest-docs`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Turn existing design documents into project memory.

Delegation: contain. Orchestrator role: locate sources, contain GSD's ingestion including conflict detection, then fold decisions into the GDD ledger.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-ingest-docs.md
@<gsd-core>/workflows/ingest-docs.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (conflict surfacing, no auto-resolution of design conflicts).
</process>
