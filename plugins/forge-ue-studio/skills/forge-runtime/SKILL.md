---
name: forge-runtime
description: Inspect, assign, or swap the resident AI runtime host without losing project state
---

<invocation>
- Invoked by naming `forge-runtime`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Manage the runtime assignment recorded in `.forge/runtime.json`.

Delegation: native. Renders every host surface from canon, so a swap is reversible and byte-identical on return.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-runtime.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (prerequisite contract, preview before apply, fresh-session boundary, qualification staleness).
</process>
