---
name: forge-docs-update
description: Generate or update project documentation verified against the codebase
---

<invocation>
- Invoked by naming `forge-docs-update`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Refresh documentation after implementation lands.

Delegation: contain. Orchestrator role: contain GSD's doc writers and verifier, then reconcile the GDD ledger and asset-interface registry.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-docs-update.md
@<gsd-core>/workflows/docs-update.md
@<forge-plugin-root>/references/delegation-contract.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (codebase verification, ledger consistency).
</process>
