---
name: forge-capability-admin
description: Register, consent to, qualify, activate, and route optional capabilities
---

<invocation>
- Invoked by naming `forge-capability-admin`. The active host supplies the prefix.
- Treat all user text after the name as `{{FORGE_ARGS}}`.
- Treat `{{FORGE_ARGS}}` as empty when no arguments are present.
</invocation>

<objective>
Manage optional capability surfaces without changing Forge's permanent directives.

Delegation: native. Orchestrator role: register contracts, obtain scoped consent, qualify per task class, and activate the smallest surface.
</objective>

<execution_context>
@<forge-plugin-root>/workflows/forge-capability-admin.md
@<forge-plugin-root>/skills/forge-capability-admin/references/lifecycle.md
</execution_context>

<context>
Arguments: {{FORGE_ARGS}}
</context>

<process>
Execute the Forge workflow end-to-end.
Preserve every Forge gate (consent before external effect, qualification per task class, smallest activation, scope discipline).
</process>
